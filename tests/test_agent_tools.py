import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from library_management_system.agent.tools import create_library_tools
from library_management_system.dao import Book, BookAvailability


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        assert text == "space exploration"
        return [0.1] * 1536


def test_search_tool_formats_catalog_results(monkeypatch) -> None:
    book = Book(
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


def test_recommendation_tool_uses_embedder_and_default_limit(monkeypatch) -> None:
    book = Book(
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
