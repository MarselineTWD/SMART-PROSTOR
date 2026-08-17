from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np

from backend.app.core.config import settings


class EmbeddingsService:
    """Wrapper around sentence-transformers with e5 prefix handling.

    The e5 model family expects `query:` prefix for search queries and
    `passage:` prefix for the indexed documents. Producing embeddings without
    the prefix silently degrades retrieval quality, so we handle it here.
    """

    def __init__(self, model_name: str, device: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device=device)
        self._is_e5 = "e5" in model_name.lower()

    def _wrap(self, texts: Iterable[str], kind: str) -> list[str]:
        if not self._is_e5:
            return list(texts)
        prefix = "query: " if kind == "query" else "passage: "
        return [prefix + (t or "") for t in texts]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prepared = self._wrap(texts, "passage")
        vectors = self._model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return _as_lists(vectors)

    def embed_query(self, text: str) -> list[float]:
        prepared = self._wrap([text], "query")
        vector = self._model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        return vector.tolist()


def _as_lists(matrix: np.ndarray) -> list[list[float]]:
    return [row.tolist() for row in matrix]


@lru_cache(maxsize=1)
def get_embeddings_service() -> EmbeddingsService:
    return EmbeddingsService(
        model_name=settings.embedding_model_name,
        device=settings.embedding_device,
    )
