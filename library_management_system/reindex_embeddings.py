from math import isfinite
from uuid import UUID

from sqlalchemy import select, update

from library_management_system.config import get_settings
from library_management_system.dao import (
    Book,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from library_management_system.services import book_embedding_text, get_embeddings

BATCH_SIZE = 100


def reindex_book_embeddings(batch_size: int = BATCH_SIZE) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    settings = get_settings()
    engine = create_database_engine()
    sessions = create_session_factory(engine)
    updated_count = 0
    last_id: UUID | None = None

    try:
        embedder = get_embeddings()
        while True:
            statement = select(Book.id, Book.genre, Book.synopsis).order_by(Book.id)
            if last_id is not None:
                statement = statement.where(Book.id > last_id)
            statement = statement.limit(batch_size)

            with session_scope(sessions) as session:
                books = session.execute(statement).all()
            if not books:
                break

            last_id = books[-1].id
            texts = [
                book_embedding_text(genre, synopsis)
                for _, genre, synopsis in books
            ]
            embedding_texts = [text for text in texts if text is not None]
            vectors = (
                embedder.embed_documents(embedding_texts)
                if embedding_texts
                else []
            )
            if len(vectors) != sum(text is not None for text in texts):
                raise RuntimeError(
                    "Embedding service returned an unexpected result count."
                )

            updates = []
            vector_index = 0
            for (book_id, _, _), text in zip(books, texts, strict=True):
                vector = vectors[vector_index] if text is not None else None
                if text is not None:
                    vector_index += 1
                    if len(vector) != settings.synopsis_embedding_dimensions:
                        raise ValueError(
                            "Embedding service returned an unexpected vector "
                            f"dimension for book {book_id}."
                        )
                    if not all(isfinite(value) for value in vector):
                        raise ValueError(
                            f"Embedding for book {book_id} contains "
                            "a non-finite value."
                        )
                    updated_count += 1
                updates.append((book_id, vector))

            with session_scope(sessions) as session:
                for book_id, vector in updates:
                    session.execute(
                        update(Book)
                        .where(Book.id == book_id)
                        .values(synopsis_embedding=vector)
                    )
    finally:
        engine.dispose()

    return updated_count


def main() -> None:
    updated = reindex_book_embeddings()
    print(f"Re-embedded {updated} book(s) with genre and synopsis.")


if __name__ == "__main__":
    main()
