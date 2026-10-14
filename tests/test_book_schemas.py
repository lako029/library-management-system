from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from library_management_system.dao import BookAvailability
from library_management_system.data_models import (BookCreate, BookRead,
                                                   BookUpdate)


def test_book_create_strips_required_text_and_applies_defaults() -> None:
    book = BookCreate(title="  Dune  ", author=" Frank Herbert ")

    assert book.title == "Dune"
    assert book.author == "Frank Herbert"
    assert book.availability is BookAvailability.AVAILABLE
    assert book.synopsis is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("title", "  "), ("author", "  ")],
)
def test_book_create_rejects_blank_required_text(field: str, value: str) -> None:
    payload = {"title": "Dune", "author": "Frank Herbert"}
    payload[field] = value

    with pytest.raises(ValidationError):
        BookCreate(**payload)


def test_book_update_requires_full_replacement_payload() -> None:
    with pytest.raises(ValidationError):
        BookUpdate.model_validate({})

    update = BookUpdate(
        title="Dune",
        author="Frank Herbert",
        isbn=None,
        synopsis=None,
        genre=None,
        publication_year=None,
        language=None,
        availability=BookAvailability.AVAILABLE,
    )
    assert update.synopsis is None


def test_book_read_loads_orm_attributes_without_embedding() -> None:
    book = SimpleNamespace(
        id=uuid4(),
        title="Dune",
        author="Frank Herbert",
        isbn=None,
        synopsis="A desert world.",
        genre="Science fiction",
        publication_year=1965,
        language="English",
        availability=BookAvailability.AVAILABLE,
        checked_out_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        synopsis_embedding=[0.1, 0.2],
    )

    result = BookRead.model_validate(book)

    assert result.id == book.id
    assert result.checked_out_by is None
    assert "synopsis_embedding" not in result.model_dump()
