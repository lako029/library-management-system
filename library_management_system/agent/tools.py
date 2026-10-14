import json
from collections.abc import Sequence
from typing import Literal, Protocol

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.dao import (Book, BookAvailability,
                                           BookAvailabilityError, BookDAO,
                                           create_database_engine,
                                           create_session_factory,
                                           session_scope)
from library_management_system.services.embeddings import get_embeddings

AvailabilityFilter = Literal["all", "available", "borrowed"]


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


def create_library_tools(
    sessions: sessionmaker[Session] | None = None,
    *,
    embedder: QueryEmbedder | None = None,
    borrower_id: str | None = None,
) -> list[BaseTool]:
    """Create catalog tools, adding borrower-scoped actions when authenticated."""
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

    tools = [search_books, recommend_books]
    if borrower_id is not None:

        @tool
        def check_out_book(
            title: str,
            author: str = "",
            publication_year: int | None = None,
        ) -> str:
            """Check out an available book for the currently signed-in patron.

            Use the exact catalog title. Provide the author when needed to
            distinguish books with the same title, and the year when needed
            to distinguish editions.
            """
            return _change_book_status(
                sessions,
                title=title,
                author=author,
                publication_year=publication_year,
                borrower_id=borrower_id,
                check_out=True,
            )

        @tool
        def check_in_book(
            title: str,
            author: str = "",
            publication_year: int | None = None,
        ) -> str:
            """Check in a book currently borrowed by the signed-in patron.

            Use the exact catalog title. Provide the author when needed to
            distinguish books with the same title, and the year when needed
            to distinguish editions. Only the patron who checked out a book
            can check it in.
            """
            return _change_book_status(
                sessions,
                title=title,
                author=author,
                publication_year=publication_year,
                borrower_id=borrower_id,
                check_out=False,
            )

        tools.extend([check_out_book, check_in_book])
    return tools


def _change_book_status(
    sessions: sessionmaker[Session],
    *,
    title: str,
    author: str,
    publication_year: int | None,
    borrower_id: str,
    check_out: bool,
) -> str:
    exact_title = title.strip()
    exact_author = author.strip()
    if not exact_title:
        return json.dumps(
            {"success": False, "message": "Provide the book's exact title."}
        )

    try:
        with session_scope(sessions) as session:
            dao = BookDAO(session)
            matches = [
                book
                for book in dao.search(exact_title, limit=100)
                if book.title.casefold() == exact_title.casefold()
                and (
                    not exact_author
                    or book.author.casefold() == exact_author.casefold()
                )
                and (
                    publication_year is None
                    or book.publication_year == publication_year
                )
            ]
            if not matches:
                return json.dumps(
                    {
                        "success": False,
                        "message": (
                            f"No exact catalog match for “{exact_title}”"
                            + (f" by {exact_author}" if exact_author else "")
                            + "."
                        ),
                    }
                )
            if len(matches) > 1:
                return json.dumps(
                    {
                        "success": False,
                        "message": (
                            "More than one book matches. Ask the patron to "
                            "specify the author or publication year."
                        ),
                        "matches": [
                            {
                                "title": book.title,
                                "author": book.author,
                                "publication_year": book.publication_year,
                            }
                            for book in matches
                        ],
                    }
                )

            book = matches[0]
            updated = (
                dao.check_out(book.id, borrower_id)
                if check_out
                else dao.check_in(book.id, borrower_id)
            )
            if updated is None:
                return json.dumps(
                    {
                        "success": False,
                        "message": "That book is no longer in the catalog.",
                    }
                )
            result_book = {
                "title": updated.title,
                "author": updated.author,
                "availability": updated.availability.value,
            }
    except BookAvailabilityError as error:
        return json.dumps({"success": False, "message": str(error)})

    action = "out" if check_out else "in"
    return json.dumps(
        {
            "success": True,
            "message": (
                f"Successfully checked {action} “{result_book['title']}” "
                f"by {result_book['author']}."
            ),
            "book": result_book,
        }
    )


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
