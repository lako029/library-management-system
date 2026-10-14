import json
from collections.abc import Sequence
from typing import Literal, Protocol

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.dao import (
    Book,
    BookAvailability,
    BookDAO,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from library_management_system.services.embeddings import get_embeddings

AvailabilityFilter = Literal["all", "available", "borrowed"]


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


def create_library_tools(
    sessions: sessionmaker[Session] | None = None,
    *,
    embedder: QueryEmbedder | None = None,
) -> list[BaseTool]:
    """Create read-only book search and synopsis-recommendation tools."""
    if sessions is None:
        engine = create_database_engine()
        sessions = create_session_factory(engine)

    @tool
    def search_books(
        query: str = "",
        availability: AvailabilityFilter = "all",
        limit: int = 10,
    ) -> str:
        """Search the library catalog by title, author, ISBN, genre, or synopsis.

        Args:
            query: Search terms. Use an empty string to browse the catalog.
            availability: Filter to all books, available books, or borrowed books.
            limit: Maximum number of results to return, from 1 to 100.
        """
        status = {
            "all": None,
            "available": BookAvailability.AVAILABLE,
            "borrowed": BookAvailability.BORROWED,
        }[availability]
        with session_scope(sessions) as session:
            books = BookDAO(session).search(
                query,
                availability=status,
                limit=limit,
            )
        return _format_books(books)

    @tool
    def recommend_books(
        description: str,
        limit: int = 3,
        available_only: bool = True,
    ) -> str:
        """Recommend books with synopsis embeddings similar to a reader's request.

        Uses text-embedding-3-small and Euclidean distance over book synopsis
        embeddings. A smaller distance means a closer match. Books need a synopsis
        embedding to be considered.

        Args:
            description: A topic, premise, mood, or other recommendation request.
            limit: Maximum number of recommendations, from 1 to 100.
            available_only: Whether to only include books currently available.
        """
        if not description.strip():
            raise ValueError("description must not be empty.")
        query_embedder = embedder or get_embeddings()
        query_vector = query_embedder.embed_query(description.strip())
        with session_scope(sessions) as session:
            books = BookDAO(session).recommend_by_embedding(
                query_vector,
                limit=limit,
                available_only=available_only,
            )
        if not books:
            return json.dumps(
                {
                    "message": (
                        "No matching books with synopsis embeddings were found."
                    ),
                    "results": [],
                }
            )
        return _format_books(books)

    return [search_books, recommend_books]


def _format_books(books: Sequence[Book]) -> str:
    results = []
    for book in books:
        results.append(
            {
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "genre": book.genre,
                "publication_year": book.publication_year,
                "language": book.language,
                "synopsis": book.synopsis,
                "availability": book.availability.value,
            }
        )
    return json.dumps({"results": results})