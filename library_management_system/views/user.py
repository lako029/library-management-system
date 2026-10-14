from collections.abc import Callable
from uuid import UUID

import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.agent.agent import run_agent
from library_management_system.dao import (
    Book,
    BookAvailability,
    BookAvailabilityError,
    BookDAO,
    session_scope,
)

SessionFactory = sessionmaker[Session]


def render_user_view(sessions: SessionFactory) -> None:
    st.header("Browse the catalog")
    st.markdown(
        """
        <style>
        .availability-badge {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }
        .availability-available {
            color: #176b36;
            background: #e7f5eb;
        }
        .availability-borrowed {
            color: #8a4b08;
            background: #fff2d8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    search_text = st.text_input(
        "Search by title, author, ISBN, genre, or synopsis",
        key="user_search",
    )
    availability_filter = st.selectbox(
        "Availability",
        ("All books", "Available", "Borrowed"),
        key="user_availability_filter",
    )
    availability = {
        "All books": None,
        "Available": BookAvailability.AVAILABLE,
        "Borrowed": BookAvailability.BORROWED,
    }[availability_filter]

    try:
        with session_scope(sessions) as session:
            books = BookDAO(session).search(
                search_text,
                availability=availability,
                limit=100,
            )
    except SQLAlchemyError as error:
        st.error(f"Could not load books ({type(error).__name__}). Try again.")
        return

    if not books:
        st.info("No books match your search.")
    else:
        st.caption(f"{len(books)} book(s)")
        for book in books:
            with st.container(border=True):
                title_column, status_column, action_column = st.columns([5, 2, 1])
                with title_column:
                    st.subheader(book.title)
                    details = [book.author]
                    if book.publication_year is not None:
                        details.append(str(book.publication_year))
                    if book.genre:
                        details.append(book.genre)
                    st.caption(" · ".join(details))
                    if book.synopsis:
                        st.write(book.synopsis)
                    if book.isbn:
                        st.caption(f"ISBN: {book.isbn}")
                with status_column:
                    _render_availability_badge(book.availability)
                with action_column:
                    _render_user_book_action(sessions, book)

    _render_assistant_chat(sessions)


def _render_availability_badge(availability: BookAvailability) -> None:
    status_class = (
        "availability-available"
        if availability == BookAvailability.AVAILABLE
        else "availability-borrowed"
    )
    st.markdown(
        f'<span class="availability-badge {status_class}">'
        f"{availability.value.title()}</span>",
        unsafe_allow_html=True,
    )


def _render_assistant_chat(sessions: SessionFactory) -> None:
    st.divider()
    st.subheader("Ask the librarian")
    st.caption(
        "Search the catalog or get synopsis-based recommendations. "
        "Assistant requests require OPENAI_API_KEY."
    )
    if st.button("Clear conversation", key="clear_librarian_chat"):
        st.session_state["librarian_chat"] = []
        st.rerun()

    messages: list[dict[str, str]] = st.session_state.setdefault(
        "librarian_chat", []
    )
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about books or describe what you enjoy"):
        history: list[BaseMessage] = [
            HumanMessage(content=message["content"])
            if message["role"] == "user"
            else AIMessage(content=message["content"])
            for message in messages
        ]
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Searching the library..."):
                    response = run_agent(
                        prompt,
                        sessions=sessions,
                        history=history,
                    )
            except OpenAIError as error:
                st.error(
                    f"The assistant request failed ({type(error).__name__}). "
                    "Check OPENAI_API_KEY and try again."
                )
            except (RuntimeError, ValueError, SQLAlchemyError) as error:
                st.error(
                    f"The assistant could not complete the request "
                    f"({type(error).__name__}). Please try again."
                )
            else:
                st.markdown(response)
                messages.extend(
                    [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ]
                )


def _render_user_book_action(sessions: SessionFactory, book: Book) -> None:
    if book.availability == BookAvailability.AVAILABLE:
        label = "Check out"
        action: Callable[[BookDAO, UUID], Book | None] = BookDAO.check_out
        success_message = "Book checked out."
    else:
        label = "Check in"
        action = BookDAO.check_in
        success_message = "Book checked in."

    if st.button(label, key=f"user_action_{book.id}", use_container_width=True):
        try:
            with session_scope(sessions) as session:
                updated_book = action(BookDAO(session), book.id)
                if updated_book is None:
                    st.warning("This book is no longer in the catalog.")
                    return
        except BookAvailabilityError as error:
            st.warning(str(error))
            return
        except SQLAlchemyError as error:
            st.error(f"Could not update availability ({type(error).__name__}).")
            return
        st.toast(success_message)
        st.rerun()
