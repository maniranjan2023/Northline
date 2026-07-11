"""
EmbeddingService
----------------
Turns text into vectors so we can do semantic search.

A vector is just a list of numbers that represents meaning.
Similar sentences get similar vectors.
"""

from __future__ import annotations

import hashlib
import math
import re


class EmbeddingService:
    """Creates embeddings for memory search."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self._model = None
        self._use_fallback = False

    def _load_model(self) -> None:
        """Load HuggingFace model once. Falls back if install is missing."""
        if self._model is not None or self._use_fallback:
            return

        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            self._model = HuggingFaceEmbeddings(model_name=self.model_name)
        except Exception:
            # Fallback keeps the app working even without sentence-transformers.
            self._use_fallback = True

    @property
    def dimensions(self) -> int:
        """Vector size used by pgvector column."""
        return 384

    def embed(self, text: str) -> list[float]:
        """
        Convert text to an embedding vector.

        Input: any string
        Output: list[float] with fixed length (384)
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return [0.0] * self.dimensions

        self._load_model()
        if self._model is not None:
            return self._model.embed_query(clean_text)

        return self._fallback_embed(clean_text)

    def content_hash(self, text: str) -> str:
        """Create a stable hash to detect duplicate memories."""
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _fallback_embed(self, text: str) -> list[float]:
        """
        Simple deterministic embedding when HuggingFace is unavailable.

        Not as smart as a real model, but good enough for basic similarity.
        """
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        vector = [0.0] * self.dimensions

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dimensions):
                byte_value = digest[index % len(digest)]
                vector[index] += (byte_value / 255.0) - 0.5

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
