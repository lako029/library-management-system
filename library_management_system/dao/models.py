from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum as SQLAlchemyEnum,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BookAvailability(str, Enum):
    AVAILABLE = "available"
    BORROWED = "borrowed"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    isbn: Mapped[str | None] = mapped_column(String(17), unique=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    genre: Mapped[str | None] = mapped_column(String(100), index=True)
    publication_year: Mapped[int | None]
    language: Mapped[str | None] = mapped_column(String(50))
    availability: Mapped[BookAvailability] = mapped_column(
        SQLAlchemyEnum(
            BookAvailability,
            name="book_availability",
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        default=BookAvailability.AVAILABLE,
        server_default=BookAvailability.AVAILABLE.value,
    )
    checked_out_by: Mapped[str | None] = mapped_column(String(255))
    synopsis_embedding: Mapped[list[float] | None] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
