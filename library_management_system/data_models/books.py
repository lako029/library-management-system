from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from library_management_system.dao.models import BookAvailability


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(min_length=1, max_length=300)
    isbn: str | None = Field(max_length=17)
    synopsis: str | None
    genre: str | None = Field(max_length=100)
    publication_year: int | None = Field(ge=0)
    language: str | None = Field(max_length=50)
    availability: BookAvailability

    @field_validator("title", "author")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class BookCreate(BookBase):
    isbn: str | None = None
    synopsis: str | None = None
    genre: str | None = Field(default=None, max_length=100)
    publication_year: int | None = Field(default=None, ge=0)
    language: str | None = Field(default=None, max_length=50)
    availability: BookAvailability = BookAvailability.AVAILABLE


class BookUpdate(BookBase):
    """Complete replacement payload for an existing book."""


class BookRead(BookBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    checked_out_by: str | None = None
    created_at: datetime
    updated_at: datetime
