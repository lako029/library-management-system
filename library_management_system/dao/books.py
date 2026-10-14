from collections.abc import Sequence
from math import isfinite
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from library_management_system.config import get_settings
from library_management_system.dao.models import (Book, BookAvailability,
                                                  BookReview)
from library_management_system.data_models import BookCreate, BookUpdate

MAX_QUERY_LIMIT = 100


class BookAvailabilityError(ValueError):
    """Raised when a check-in/check-out transition is not valid."""


class BookDAO:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        data: BookCreate,
        *,
        synopsis_embedding: Sequence[float] | None = None,
    ) -> Book:
        if data.availability is not BookAvailability.AVAILABLE:
            raise BookAvailabilityError(
                "New books must be available; use check_out to borrow a book."
            )
        book = Book(
            **data.model_dump(),
            checked_out_by=None,
            synopsis_embedding=(
                _validate_embedding(synopsis_embedding)
                if synopsis_embedding is not None
                else None
            ),
        )
        self._session.add(book)
        self._session.flush()
        return book

    def get(self, book_id: UUID) -> Book | None:
        return self._session.get(Book, book_id)

    def search(
        self,
        query: str = "",
        *,
        availability: BookAvailability | None = None,
        limit: int = 20,
    ) -> list[Book]:
        _validate_limit(limit)
        statement: Select[tuple[Book]] = select(Book)
        search_text = query.strip()
        if search_text:
            pattern = f"%{search_text}%"
            statement = statement.where(
                Book.title.ilike(pattern)
                | Book.author.ilike(pattern)
                | Book.isbn.ilike(pattern)
                | Book.genre.ilike(pattern)
                | Book.synopsis.ilike(pattern)
            )
        if availability is not None:
            statement = statement.where(Book.availability == availability)
        statement = statement.order_by(Book.title, Book.author).limit(limit)
        return list(self._session.scalars(statement).all())

    def update(
        self,
        book_id: UUID,
        data: BookUpdate,
        *,
        synopsis_embedding: Sequence[float] | None = None,
    ) -> Book | None:
        statement = select(Book).where(Book.id == book_id).with_for_update()
        book = self._session.scalars(statement).one_or_none()
        if book is None:
            return None
        previous_synopsis = book.synopsis
        previous_genre = book.genre
        if (
            data.availability is BookAvailability.BORROWED
            and book.availability is BookAvailability.AVAILABLE
        ):
            raise BookAvailabilityError(
                "Use check_out to borrow a book so its borrower is recorded."
            )
        for field, value in data.model_dump().items():
            setattr(book, field, value)
        if data.availability is BookAvailability.AVAILABLE:
            book.checked_out_by = None
        if synopsis_embedding is not None:
            book.synopsis_embedding = _validate_embedding(synopsis_embedding)
        elif data.synopsis != previous_synopsis or data.genre != previous_genre:
            book.synopsis_embedding = None
        self._session.flush()
        return book

    def delete(self, book_id: UUID) -> bool:
        book = self.get(book_id)
        if book is None:
            return False
        self._session.delete(book)
        self._session.flush()
        return True

    def check_out(self, book_id: UUID, borrower_id: str) -> Book | None:
        _validate_borrower_id(borrower_id)
        return self._set_availability(
            book_id,
            expected=BookAvailability.AVAILABLE,
            target=BookAvailability.BORROWED,
            borrower_id=borrower_id,
        )

    def check_in(
        self,
        book_id: UUID,
        borrower_id: str,
        rating: int | None = None,
    ) -> Book | None:
        _validate_borrower_id(borrower_id)
        _validate_rating(rating)
        return self._set_availability(
            book_id,
            expected=BookAvailability.BORROWED,
            target=BookAvailability.AVAILABLE,
            borrower_id=borrower_id,
            rating=rating,
        )

    def recommend_by_embedding(
        self,
        embedding: Sequence[float],
        *,
        limit: int = 10,
        available_only: bool = False,
    ) -> list[Book]:
        _validate_limit(limit)
        vector = _validate_embedding(embedding)
        distance = Book.synopsis_embedding.l2_distance(vector)
        statement = (
            select(Book)
            .where(Book.synopsis_embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if available_only:
            statement = statement.where(Book.availability == BookAvailability.AVAILABLE)
        return list(self._session.scalars(statement).all())

    def _set_availability(
        self,
        book_id: UUID,
        *,
        expected: BookAvailability,
        target: BookAvailability,
        borrower_id: str,
        rating: int | None = None,
    ) -> Book | None:
        statement = select(Book).where(Book.id == book_id).with_for_update()
        book = self._session.scalars(statement).one_or_none()
        if book is None:
            return None
        if book.availability != expected:
            raise BookAvailabilityError(
                f"Cannot change availability from {book.availability.value} "
                f"to {target.value}."
            )
        if target is BookAvailability.AVAILABLE:
            if book.checked_out_by != borrower_id:
                raise BookAvailabilityError(
                    "Only the user who checked out this book can check it in."
                )
            if rating is not None:
                self._session.add(
                    BookReview(
                        book_id=book.id,
                        borrower_id=borrower_id,
                        rating=rating,
                    )
                )
            book.checked_out_by = None
        else:
            book.checked_out_by = borrower_id
        book.availability = target
        self._session.flush()
        return book


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_QUERY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_QUERY_LIMIT}.")


def _validate_borrower_id(borrower_id: str) -> None:
    if not borrower_id or not borrower_id.strip():
        raise ValueError("borrower_id must not be blank.")
    if len(borrower_id) > 255:
        raise ValueError("borrower_id must be at most 255 characters.")


def _validate_rating(rating: int | None) -> None:
    if rating is not None and (
        not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5
    ):
        raise ValueError("rating must be between 1 and 5.")


def _validate_embedding(embedding: Sequence[float]) -> list[float]:
    vector = [float(value) for value in embedding]
    dimensions = get_settings().synopsis_embedding_dimensions
    if len(vector) != dimensions:
        raise ValueError(f"embedding must contain {dimensions} values.")
    if not all(isfinite(value) for value in vector):
        raise ValueError("embedding values must all be finite.")
    return vector
