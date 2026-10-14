import os
from math import isfinite

from langchain_openai import OpenAIEmbeddings

from library_management_system.config import get_settings


def get_embeddings() -> OpenAIEmbeddings:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY to use synopsis embeddings.")
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.synopsis_embedding_model,
        dimensions=settings.synopsis_embedding_dimensions,
    )


def embed_synopsis(synopsis: str | None) -> list[float] | None:
    if synopsis is None or not synopsis.strip():
        return None

    dimensions = get_settings().synopsis_embedding_dimensions
    embedding = get_embeddings().embed_query(synopsis.strip())
    if len(embedding) != dimensions:
        raise ValueError(
            f"Expected {dimensions} embedding values, "
            f"received {len(embedding)}."
        )
    if not all(isfinite(value) for value in embedding):
        raise ValueError("Synopsis embedding contains a non-finite value.")
    return embedding
