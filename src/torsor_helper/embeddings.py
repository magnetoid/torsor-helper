from __future__ import annotations

import hashlib
import math
import re
import warnings
from typing import Protocol, Sequence, runtime_checkable

_WORD = re.compile(r"\w+")


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic, dependency-free bag-of-words hashing embedder.

    Stable across processes (uses md5, not Python's salted hash). Used in tests
    and as the fallback when fastembed is unavailable.
    """

    name = "hashing"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in _WORD.findall(text.lower()):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            out.append(vec)
        return out


class FastEmbedEmbedder:
    """Local ONNX embeddings via the optional `fastembed` extra (lazy-loaded)."""

    name = "fastembed"

    def __init__(self, model: str) -> None:
        self.model = model
        self._model = _make_fastembed(model)
        probe = next(iter(self._model.embed(["x"])))
        self.dim = len(list(probe))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.embed(list(texts))]


def _make_fastembed(model: str):  # pragma: no cover - exercised only when installed
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model)


def get_embedder(config) -> Embedder:
    if config.embeddings.provider == "fastembed":
        try:
            return FastEmbedEmbedder(config.embeddings.model)
        except Exception as exc:
            warnings.warn(
                f"fastembed unavailable ({exc}); falling back to HashingEmbedder. "
                "Install with `pip install torsor-helper[embeddings]` for semantic recall.",
                stacklevel=2,
            )
    return HashingEmbedder(config.embeddings.dim)
