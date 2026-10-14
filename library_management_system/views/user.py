import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.agent.agent import run_agent
from library_management_system.dao import (Book, BookAvailability,
                                           BookAvailabilityError, BookDAO,
                                           session_scope)

SessionFactory = sessionmaker[Session]


def render_user_view(sessions: SessionFactory, user_id: str) -> None:
    st.title("Find your next read")
    st.caption("Explore the collection, or ask your AI librarian for a suggestion.")
    search_column, filter_column = st.columns([3, 1], gap="large")
    with search_column:
        search_text = st.text_input(
            "Search the collection",
            placeholder="Title, author, ISBN, genre, or synopsis",
            key="user_search",
        )
    with filter_column:
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
        st.info("No books match those filters. Try another search.")
    else:
        st.caption(f"{len(books)} titles")
        for index in range(0, len(books), 2):
            columns = st.columns(2, gap="large")
            for column, book in zip(columns, books[index : index + 2]):
                with column:
                    _render_book_card(sessions, book, user_id)

    _render_assistant_chat(sessions, user_id)


def _render_book_card(
    sessions: SessionFactory,
    book: Book,
    user_id: str,
) -> None:
    with st.container(border=True):
        st.subheader(book.title)
        st.caption(book.author)
        _render_availability_badge(book.availability)
        if book.average_rating is not None:
            st.caption(
                f"★ {book.average_rating:.1f} · " f"{book.rating_count} rating(s)"
            )

        details = []
        if book.publication_year is not None:
            details.append(str(book.publication_year))
        if book.genre:
            details.append(book.genre)
        if details:
            st.caption(" · ".join(details))
        if book.synopsis:
            st.write(book.synopsis)
        if book.isbn:
            st.caption(f"ISBN {book.isbn}")

        _render_user_book_action(sessions, book, user_id)


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


def _render_assistant_chat(sessions: SessionFactory, user_id: str) -> None:
    st.divider()
    st.subheader("Your AI librarian")
    st.caption(
        "Ask about the collection, get synopsis-based recommendations, "
        "or ask to check out or return one of your books."
    )
    if st.button("Clear conversation", key="clear_librarian_chat"):
        st.session_state["librarian_chat"] = []
        st.rerun()

    messages: list[dict[str, str]] = st.session_state.setdefault("librarian_chat", [])
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(
        "Ask about books, recommendations, checkouts, or returns"
    ):
        history: list[BaseMessage] = [
            (
                HumanMessage(content=message["content"])
                if message["role"] == "user"
                else AIMessage(content=message["content"])
            )
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
                        borrower_id=user_id,
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


def _render_user_book_action(
    sessions: SessionFactory,
    book: Book,
    user_id: str,
) -> None:
    if book.availability == BookAvailability.AVAILABLE:
        label = "Check out"
        success_message = "Book checked out."
        rating = None
        check_in = False
    elif book.checked_out_by == user_id:
        st.caption("Rate this book before returning it (optional).")
        rating_index = st.feedback(
            "stars",
            key=f"user_rating_{book.id}",
        )
        rating = rating_index + 1 if rating_index is not None else None
        label = "Check in"
        check_in = True
        success_message = (
            f"Book checked in with your {rating}-star rating."
            if rating is not None
            else "Book checked in."
        )
    else:
        st.caption("Only the borrower can check in this book.")
        return

    if st.button(label, key=f"user_action_{book.id}", use_container_width=True):
        try:
            with session_scope(sessions) as session:
                dao = BookDAO(session)
                updated_book = (
                    dao.check_in(book.id, user_id, rating=rating)
                    if check_in
                    else dao.check_out(book.id, user_id)
                )
                if updated_book is None:
                    st.warning("This book is no longer in the catalog.")
                    return
        except BookAvailabilityError as error:
            st.warning(str(error))
            return
        except SQLAlchemyError as error:
            st.error(f"Could not update availability ({type(error).__name__}).")
            return
        if check_in:
            st.session_state.pop(f"user_rating_{book.id}", None)
        st.toast(success_message)
        st.rerun()
