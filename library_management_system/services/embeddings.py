import os
from math import isfinite

from langchain_openai import OpenAIEmbeddings

from library_management_system.config import get_settings


def get_embeddings() -> OpenAIEmbeddings:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY to use book embeddings.")
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.synopsis_embedding_model,
        dimensions=settings.synopsis_embedding_dimensions,
    )


def book_embedding_text(genre: str | None, synopsis: str | None) -> str | None:
    sections = []
    if genre and genre.strip():
        sections.append(f"Genre: {genre.strip()}")
    if synopsis and synopsis.strip():
        sections.append(f"Synopsis: {synopsis.strip()}")
    if not sections:
        return None
    return "\n".join(sections)


def embed_book_content(
    genre: str | None,
    synopsis: str | None,
) -> list[float] | None:
    text = book_embedding_text(genre, synopsis)
    if text is None:
        return None
    dimensions = get_settings().synopsis_embedding_dimensions
    embedding = get_embeddings().embed_query(text)
    if len(embedding) != dimensions:
        raise ValueError(
            f"Expected {dimensions} embedding values, " f"received {len(embedding)}."
        )
    if not all(isfinite(value) for value in embedding):
        raise ValueError("Synopsis embedding contains a non-finite value.")
    return embedding
