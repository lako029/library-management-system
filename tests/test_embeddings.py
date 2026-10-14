from sqlalchemy import create_engine, select

from library_management_system import reindex_embeddings
from library_management_system.dao import Base, Book
from library_management_system.services.embeddings import (
    book_embedding_text,
    embed_book_content,
)


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1] * 1536


def test_book_embedding_text_includes_genre_and_synopsis() -> None:
    assert book_embedding_text("Science fiction", "A Mars mission.") == (
        "Genre: Science fiction\nSynopsis: A Mars mission."
    )
    assert book_embedding_text("  ", "  A Mars mission.  ") == (
        "Synopsis: A Mars mission."
    )
    assert book_embedding_text(None, None) is None


def test_embed_book_content_uses_combined_text(monkeypatch) -> None:
    embedder = FakeEmbedder()
    monkeypatch.setattr(
        "library_management_system.services.embeddings.get_embeddings",
        lambda: embedder,
    )

    result = embed_book_content("Science fiction", "A Mars mission.")

    assert result == [0.1] * 1536
    assert embedder.queries == [
        "Genre: Science fiction\nSynopsis: A Mars mission."
    ]


def test_reindex_updates_existing_vectors_with_genre_and_synopsis(
    monkeypatch,
    tmp_path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'library.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            Book.__table__.insert(),
            [
                {
                    "title": "Dune",
                    "author": "Frank Herbert",
                    "genre": "Science fiction",
                    "synopsis": "A desert planet.",
                    "availability": "available",
                    "synopsis_embedding": [0.2] * 1536,
                },
                {
                    "title": "Unknown",
                    "author": "Unknown",
                    "genre": None,
                    "synopsis": None,
                    "availability": "available",
                    "synopsis_embedding": [0.3] * 1536,
                },
            ],
        )

    class FakeBatchEmbedder:
        texts: list[str] = []

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.texts.extend(texts)
            return [[0.4] * 1536 for _ in texts]

    embedder = FakeBatchEmbedder()
    monkeypatch.setattr(
        "library_management_system.reindex_embeddings.create_database_engine",
        lambda: engine,
    )
    monkeypatch.setattr(
        "library_management_system.reindex_embeddings.get_embeddings",
        lambda: embedder,
    )

    updated = reindex_embeddings.reindex_book_embeddings(batch_size=1)

    assert updated == 1
    assert embedder.texts == ["Genre: Science fiction\nSynopsis: A desert planet."]
    with engine.connect() as connection:
        embeddings = connection.execute(
            select(Book.synopsis_embedding).order_by(Book.title)
        ).scalars().all()
    assert embeddings == [[0.4] * 1536, None]
