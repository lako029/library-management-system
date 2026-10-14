from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from library_management_system.dao import (
    Book,
    BookAvailability,
    BookAvailabilityError,
    BookDAO,
)
from library_management_system.data_models import BookCreate, BookUpdate


def _complete_update(
    *,
    synopsis: str | None = "Updated synopsis",
) -> BookUpdate:
    return BookUpdate(
        title="Dune",
        author="Frank Herbert",
        isbn=None,
        synopsis=synopsis,
        genre="Science fiction",
        publication_year=1965,
        language="English",
        availability=BookAvailability.AVAILABLE,
    )


def test_create_adds_book_and_flushes_session() -> None:
    session = MagicMock()

    book = BookDAO(session).create(BookCreate(title="Dune", author="Frank Herbert"))

    assert book.title == "Dune"
    assert book.availability is BookAvailability.AVAILABLE
    session.add.assert_called_once_with(book)
    session.flush.assert_called_once()


def test_update_replaces_fields_and_clears_stale_embedding() -> None:
    session = MagicMock()
    book = Book(
        id=uuid4(),
        title="Dune",
        author="Frank Herbert",
        synopsis="Original synopsis",
        synopsis_embedding=[0.1] * 1536,
    )
    session.get.return_value = book

    result = BookDAO(session).update(book.id, _complete_update())

    assert result is book
    assert result.synopsis == "Updated synopsis"
    assert result.synopsis_embedding is None
    session.flush.assert_called_once()


def test_update_keeps_embedding_when_synopsis_is_unchanged() -> None:
    session = MagicMock()
    embedding = [0.1] * 1536
    book = Book(
        id=uuid4(),
        title="Dune",
        author="Frank Herbert",
        synopsis="Updated synopsis",
        synopsis_embedding=embedding,
    )
    session.get.return_value = book

    BookDAO(session).update(book.id, _complete_update())

    assert book.synopsis_embedding == embedding


def test_update_returns_none_for_unknown_book() -> None:
    session = MagicMock()
    session.get.return_value = None

    assert BookDAO(session).update(uuid4(), _complete_update()) is None
    session.flush.assert_not_called()


def test_delete_returns_false_for_unknown_book() -> None:
    session = MagicMock()
    session.get.return_value = None

    assert BookDAO(session).delete(uuid4()) is False
    session.delete.assert_not_called()


def test_check_out_and_check_in_lock_and_change_availability() -> None:
    session = MagicMock()
    book = Book(
        id=uuid4(),
        title="Dune",
        author="Frank Herbert",
        availability=BookAvailability.AVAILABLE,
    )
    session.scalars.return_value.one_or_none.return_value = book
    dao = BookDAO(session)

    assert dao.check_out(book.id) is book
    assert book.availability is BookAvailability.BORROWED
    assert dao.check_in(book.id) is book
    assert book.availability is BookAvailability.AVAILABLE
    assert session.scalars.call_count == 2
    assert session.flush.call_count == 2


def test_check_out_rejects_already_borrowed_book() -> None:
    session = MagicMock()
    book = Book(
        id=uuid4(),
        title="Dune",
        author="Frank Herbert",
        availability=BookAvailability.BORROWED,
    )
    session.scalars.return_value.one_or_none.return_value = book

    with pytest.raises(BookAvailabilityError):
        BookDAO(session).check_out(book.id)


def test_recommendation_query_orders_by_euclidean_distance() -> None:
    session = MagicMock()
    session.scalars.return_value.all.return_value = []

    assert BookDAO(session).recommend_by_embedding([0.1] * 1536) == []
    statement = session.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "<->" in sql
    assert "synopsis_embedding IS NOT NULL" in sql


@pytest.mark.parametrize("limit", [0, 101])
def test_search_rejects_out_of_range_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be between"):
        BookDAO(MagicMock()).search(limit=limit)


@pytest.mark.parametrize("embedding", [[], [float("nan")] * 1536])
def test_recommendations_reject_invalid_embeddings(
    embedding: list[float],
) -> None:
    with pytest.raises(ValueError):
        BookDAO(MagicMock()).recommend_by_embedding(embedding)
