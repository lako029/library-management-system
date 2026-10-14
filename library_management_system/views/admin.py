from typing import Any

import streamlit as st
from openai import OpenAIError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.dao import (
    Book,
    BookAvailability,
    BookDAO,
    session_scope,
)
from library_management_system.data_models import BookCreate, BookUpdate
from library_management_system.services.embeddings import embed_synopsis

SessionFactory = sessionmaker[Session]


def render_admin_view(sessions: SessionFactory) -> None:
    st.header("Admin — manage catalog")
    add_tab, edit_tab = st.tabs(("Add a book", "Edit or delete"))

    with add_tab:
        _render_create_book(sessions)
    with edit_tab:
        _render_edit_books(sessions)


def _render_create_book(sessions: SessionFactory) -> None:
    with st.form("create_book_form", clear_on_submit=True):
        values = _book_fields("create", None)
        submitted = st.form_submit_button("Add book", type="primary")
    if not submitted:
        return

    try:
        payload = BookCreate(**values)
        synopsis_embedding = embed_synopsis(payload.synopsis)
        with session_scope(sessions) as session:
            BookDAO(session).create(
                payload,
                synopsis_embedding=synopsis_embedding,
            )
    except ValidationError as error:
        _show_validation_error(error)
        return
    except (OpenAIError, RuntimeError, ValueError) as error:
        st.error(
            f"Could not index the synopsis ({type(error).__name__}). "
            "Check OPENAI_API_KEY and try again."
        )
        return
    except SQLAlchemyError as error:
        st.error(f"Could not add the book ({type(error).__name__}).")
        return
    st.success("Book added.")
    st.rerun()


def _render_edit_books(sessions: SessionFactory) -> None:
    try:
        with session_scope(sessions) as session:
            books = BookDAO(session).search(limit=100)
    except SQLAlchemyError as error:
        st.error(f"Could not load books ({type(error).__name__}).")
        return

    if not books:
        st.info("There are no books to edit yet.")
        return

    books_by_id = {str(book.id): book for book in books}
    selected_id = st.selectbox(
        "Select a book",
        options=list(books_by_id),
        format_func=lambda book_id: (
            f"{books_by_id[book_id].title} — {books_by_id[book_id].author}"
        ),
        key="admin_selected_book",
    )
    selected_book = books_by_id[selected_id]

    with st.form(f"edit_book_form_{selected_id}"):
        values = _book_fields(f"edit_{selected_id}", selected_book)
        save_submitted = st.form_submit_button("Save changes", type="primary")
    if save_submitted:
        _save_book_update(sessions, selected_book, values)

    with st.form(f"delete_book_form_{selected_id}"):
        confirm_delete = st.checkbox(
            f"Confirm deletion of “{selected_book.title}”",
            key=f"confirm_delete_{selected_id}",
        )
        delete_submitted = st.form_submit_button(
            "Delete book",
            type="secondary",
            disabled=not confirm_delete,
        )
    if delete_submitted:
        _delete_book(sessions, selected_book)


def _save_book_update(
    sessions: SessionFactory,
    selected_book: Book,
    values: dict[str, Any],
) -> None:
    try:
        payload = BookUpdate(**values)
        synopsis_embedding = (
            embed_synopsis(payload.synopsis)
            if payload.synopsis != selected_book.synopsis
            or (
                payload.synopsis is not None
                and selected_book.synopsis_embedding is None
            )
            else None
        )
        with session_scope(sessions) as session:
            updated = BookDAO(session).update(
                selected_book.id,
                payload,
                synopsis_embedding=synopsis_embedding,
            )
            if updated is None:
                st.warning("This book is no longer in the catalog.")
                return
    except ValidationError as error:
        _show_validation_error(error)
        return
    except (OpenAIError, RuntimeError, ValueError) as error:
        st.error(
            f"Could not index the synopsis ({type(error).__name__}). "
            "Check OPENAI_API_KEY and try again."
        )
        return
    except SQLAlchemyError as error:
        st.error(f"Could not update the book ({type(error).__name__}).")
        return
    st.success("Book updated.")
    st.rerun()


def _delete_book(sessions: SessionFactory, book: Book) -> None:
    try:
        with session_scope(sessions) as session:
            deleted = BookDAO(session).delete(book.id)
    except SQLAlchemyError as error:
        st.error(f"Could not delete the book ({type(error).__name__}).")
        return
    if deleted:
        st.success("Book deleted.")
        st.rerun()
    st.warning("This book is no longer in the catalog.")


def _book_fields(prefix: str, book: Book | None) -> dict[str, Any]:
    left, right = st.columns(2)
    with left:
        title = st.text_input(
            "Title",
            value=book.title if book else "",
            max_chars=500,
            key=f"{prefix}_title",
        )
        author = st.text_input(
            "Author",
            value=book.author if book else "",
            max_chars=300,
            key=f"{prefix}_author",
        )
        isbn = st.text_input(
            "ISBN",
            value=book.isbn or "" if book else "",
            max_chars=17,
            key=f"{prefix}_isbn",
        )
        genre = st.text_input(
            "Genre",
            value=book.genre or "" if book else "",
            max_chars=100,
            key=f"{prefix}_genre",
        )
    with right:
        publication_year = st.number_input(
            "Publication year (0 if unknown)",
            min_value=0,
            max_value=9999,
            value=book.publication_year or 0 if book else 0,
            step=1,
            key=f"{prefix}_publication_year",
        )
        language = st.text_input(
            "Language",
            value=book.language or "" if book else "",
            max_chars=50,
            key=f"{prefix}_language",
        )
        availability_options = list(BookAvailability)
        availability = st.selectbox(
            "Availability",
            options=availability_options,
            index=availability_options.index(book.availability)
            if book
            else availability_options.index(BookAvailability.AVAILABLE),
            format_func=lambda status: status.value.title(),
            key=f"{prefix}_availability",
        )
    synopsis = st.text_area(
        "Synopsis",
        value=book.synopsis or "" if book else "",
        key=f"{prefix}_synopsis",
    )
    return {
        "title": title,
        "author": author,
        "isbn": isbn or None,
        "synopsis": synopsis or None,
        "genre": genre or None,
        "publication_year": publication_year or None,
        "language": language or None,
        "availability": availability,
    }


def _show_validation_error(error: ValidationError) -> None:
    messages = [
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in error.errors()
    ]
    st.error("Please correct these fields: " + "; ".join(messages))
