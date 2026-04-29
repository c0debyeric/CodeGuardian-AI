"""Pluggable text embedders for the semantic cache.

The cache asks for a vector for a piece of prompt text and compares it via
cosine similarity to vectors it has seen before. The `Embedder` protocol
keeps that abstract so we can swap implementations:

  - `HashingEmbedder` (default): hashes word tokens into N buckets and
    L2-normalizes. Zero deps, deterministic, fast — good enough to catch
    "what is the capital of france" vs "what's the capital of France?"
    style near-duplicates and to demonstrate the architecture end-to-end.

  - In production you'd register a model-backed embedder (OpenAI
    `text-embedding-3-small`, Bedrock Titan Text Embeddings, or a local
    sentence-transformers model) without touching the cache code.

The cache treats vectors as opaque — only `embed()` and `dim` are required.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Token-hashing embedder. Deterministic, dependency-free.

    Each token is lowercased, hashed into one of `dim` buckets, and the
    bucket is incremented by 1. The resulting vector is L2-normalized so
    cosine similarity reduces to a dot product.

    Limitations: only catches lexical overlap (synonyms won't collide).
    Sufficient to demonstrate the wire-up; real semantic similarity needs
    a learned embedding model.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = int.from_bytes(hashlib.blake2b(tok.encode("utf-8"), digest_size=4).digest(), "big")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity for vectors that may or may not be pre-normalized."""
    if len(a) != len(b):
        raise ValueError("vector dim mismatch")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = HashingEmbedder()
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """Override the default embedder (used by tests / production wiring)."""
    global _embedder
    _embedder = embedder
