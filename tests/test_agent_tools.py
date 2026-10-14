import json
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from library_management_system.agent.tools import create_library_tools
from library_management_system.dao import (Book, BookAvailability,
                                           BookAvailabilityError)


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        assert text == "space exploration"
        return [0.1] * 1536


def test_search_tool_formats_catalog_results(monkeypatch) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        genre="Science fiction",
        publication_year=2011,
        language="English",
        synopsis="An astronaut survives on Mars.",
        availability=BookAvailability.AVAILABLE,
    )

    def search_books(
        _self,
        query: str,
        *,
        availability: BookAvailability | None,
        limit: int,
    ) -> list[Book]:
        assert _self is not None
        assert query == "Mars"
        assert availability is None
        assert limit == 10
        return [book]

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search", search_books
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    search, _ = create_library_tools(sessions, embedder=FakeEmbedder())

    result = json.loads(search.invoke({"query": "Mars"}))

    assert result["results"][0]["title"] == "The Martian"
    assert result["results"][0]["availability"] == "available"
    assert result["results"][0]["average_rating"] is None
    assert result["results"][0]["rating_count"] == 0


def test_recommendation_tool_uses_embedder_and_default_limit(monkeypatch) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        availability=BookAvailability.AVAILABLE,
    )

    def recommend_books(
        _self,
        embedding: list[float],
        *,
        limit: int,
        available_only: bool,
    ) -> list[Book]:
        assert _self is not None
        assert embedding == [0.1] * 1536
        assert limit == 3
        assert available_only is True
        return [book]

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.recommend_by_embedding",
        recommend_books,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    _, recommend = create_library_tools(sessions, embedder=FakeEmbedder())

    result = json.loads(recommend.invoke({"description": "space exploration"}))

    assert recommend.args_schema.model_fields["limit"].default == 3
    assert result["results"][0]["title"] == "The Martian"


def test_recommendation_tool_returns_empty_result_message(monkeypatch) -> None:
    def recommend_books(
        _self,
        embedding: list[float],
        *,
        limit: int,
        available_only: bool,
    ) -> list[Book]:
        assert _self is not None
        assert len(embedding) == 1536
        assert limit == 3
        assert available_only is True
        return []

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.recommend_by_embedding",
        recommend_books,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    _, recommend = create_library_tools(sessions, embedder=FakeEmbedder())

    result = json.loads(recommend.invoke({"description": "space exploration"}))

    assert result["results"] == []
    assert "No matching books" in result["message"]


def test_patron_action_tools_are_only_available_with_borrower_identity() -> None:
    sessions = sessionmaker(bind=create_engine("sqlite://"))

    assert [tool.name for tool in create_library_tools(sessions)] == [
        "search_books",
        "recommend_books",
    ]
    assert [
        tool.name for tool in create_library_tools(sessions, borrower_id="auth0|patron")
    ] == [
        "search_books",
        "recommend_books",
        "check_out_book",
        "check_in_book",
    ]


def test_check_out_tool_checks_out_exact_title_for_signed_in_patron(
    monkeypatch,
) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        availability=BookAvailability.AVAILABLE,
    )
    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search",
        lambda _self, query, *, limit: [book],
    )

    def check_out(_self, book_id, borrower_id):
        assert book_id == book.id
        assert borrower_id == "auth0|patron"
        book.availability = BookAvailability.BORROWED
        book.checked_out_by = borrower_id
        return book

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.check_out",
        check_out,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    tools = create_library_tools(sessions, borrower_id="auth0|patron")
    check_out_tool = next(tool for tool in tools if tool.name == "check_out_book")

    result = json.loads(
        check_out_tool.invoke({"title": "The Martian", "author": "Andy Weir"})
    )

    assert result["success"] is True
    assert result["book"]["availability"] == "borrowed"


def test_check_in_tool_reports_wrong_borrower_without_claiming_success(
    monkeypatch,
) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        availability=BookAvailability.BORROWED,
        checked_out_by="auth0|different-patron",
    )
    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search",
        lambda _self, query, *, limit: [book],
    )

    def check_in(_self, book_id, borrower_id, *, rating=None):
        raise BookAvailabilityError(
            "Only the user who checked out this book can check it in."
        )

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.check_in",
        check_in,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    tools = create_library_tools(sessions, borrower_id="auth0|patron")
    check_in_tool = next(tool for tool in tools if tool.name == "check_in_book")

    result = json.loads(check_in_tool.invoke({"title": "The Martian"}))

    assert result["success"] is False
    assert "Only the user" in result["message"]


def test_check_in_tool_checks_in_book_for_its_borrower(monkeypatch) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        availability=BookAvailability.BORROWED,
        checked_out_by="auth0|patron",
    )
    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search",
        lambda _self, query, *, limit: [book],
    )

    def check_in(_self, book_id, borrower_id, *, rating=None):
        assert book_id == book.id
        assert borrower_id == "auth0|patron"
        assert rating is None
        book.availability = BookAvailability.AVAILABLE
        book.checked_out_by = None
        return book

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.check_in",
        check_in,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    tools = create_library_tools(sessions, borrower_id="auth0|patron")
    check_in_tool = next(tool for tool in tools if tool.name == "check_in_book")

    result = json.loads(check_in_tool.invoke({"title": "The Martian"}))

    assert result["success"] is True
    assert result["book"]["availability"] == "available"


def test_check_in_tool_persists_the_user_rating(monkeypatch) -> None:
    book = Book(
        id=uuid4(),
        title="The Martian",
        author="Andy Weir",
        availability=BookAvailability.BORROWED,
        checked_out_by="auth0|patron",
    )
    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search",
        lambda _self, query, *, limit: [book],
    )

    def check_in(_self, book_id, borrower_id, *, rating=None):
        assert book_id == book.id
        assert borrower_id == "auth0|patron"
        assert rating == 5
        book.availability = BookAvailability.AVAILABLE
        book.checked_out_by = None
        return book

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.check_in",
        check_in,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    tools = create_library_tools(sessions, borrower_id="auth0|patron")
    check_in_tool = next(tool for tool in tools if tool.name == "check_in_book")

    result = json.loads(check_in_tool.invoke({"title": "The Martian", "rating": 5}))

    assert result["success"] is True
    assert "5-star rating" in result["message"]


def test_action_tool_requires_a_unique_exact_title_match(monkeypatch) -> None:
    books = [
        Book(
            id=uuid4(),
            title="Dune",
            author="Frank Herbert",
            publication_year=1965,
            availability=BookAvailability.AVAILABLE,
        ),
        Book(
            id=uuid4(),
            title="Dune",
            author="Brian Herbert",
            publication_year=2009,
            availability=BookAvailability.AVAILABLE,
        ),
    ]
    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.search",
        lambda _self, query, *, limit: books,
    )

    def check_out(_self, book_id, borrower_id):
        book = next(book for book in books if book.id == book_id)
        book.availability = BookAvailability.BORROWED
        book.checked_out_by = borrower_id
        return book

    monkeypatch.setattr(
        "library_management_system.agent.tools.BookDAO.check_out",
        check_out,
    )
    sessions = sessionmaker(bind=create_engine("sqlite://"))
    tools = create_library_tools(sessions, borrower_id="auth0|patron")
    check_out_tool = next(tool for tool in tools if tool.name == "check_out_book")

    result = json.loads(check_out_tool.invoke({"title": "Dune"}))
    resolved = json.loads(
        check_out_tool.invoke({"title": "Dune", "author": "Frank Herbert"})
    )

    assert result["success"] is False
    assert len(result["matches"]) == 2
    assert resolved["success"] is True
    assert resolved["book"]["author"] == "Frank Herbert"
