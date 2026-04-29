"""Semantic cache.

Two modes are supported, both behind the same `CacheBackend` interface:

  - **Exact** (`semantic_cache_mode="exact"`, default): sha256 over
    (model + canonicalized messages). Zero false positives, zero
    embedding cost. Cuts spend dramatically on bot/agent traffic where
    the same system prompt + question recurs verbatim.

  - **Semantic** (`semantic_cache_mode="semantic"`): embeds the prompt
    and returns the nearest cached entry whose cosine similarity passes
    `semantic_cache_threshold`. Catches paraphrases the exact cache
    misses ("what's the capital of France" ~ "capital of france?").
    Embedder is pluggable — see `src.middleware.embeddings`.

The cache stores the full ChatCompletionResponse, but the calling code
rewrites the gateway metadata (cache=hit, attempts=["cache"], etc.)
before returning so the client can see they got a cached result.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Protocol

from src.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from src.middleware.embeddings import cosine, get_embedder


def cache_key(request: ChatCompletionRequest) -> str:
    """Stable hash over the dimensions that determine response content."""
    payload = {
        "model": request.model,
        "messages": [
            {"role": m.role, "content": m.content if isinstance(m.content, str) else json.dumps(m.content)}
            for m in request.messages
        ],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def prompt_text(request: ChatCompletionRequest) -> str:
    """Concatenated text of all message contents — what the embedder sees.

    Multimodal/structured content is JSON-serialized so we don't crash, but
    semantic matching is only meaningful for plain-text prompts.
    """
    parts: list[str] = []
    for m in request.messages:
        if isinstance(m.content, str):
            parts.append(m.content)
        else:
            parts.append(json.dumps(m.content, sort_keys=True))
    return "\n".join(parts)


class CacheBackend(Protocol):
    async def get(self, key: str) -> ChatCompletionResponse | None: ...
    async def set(self, key: str, value: ChatCompletionResponse, *, ttl: int) -> None: ...


@dataclass
class _Entry:
    value: ChatCompletionResponse
    expires_at: float
    embedding: list[float] | None = None
    # Partition key (model id) so we never serve a Claude response to a GPT-4 request.
    namespace: str = ""
    # Original prompt text — kept only for debug/log; not used in matching.
    text: str = field(default="")


class InMemoryCache:
    """LRU cache with TTL. Bounded to keep memory predictable in dev."""

    def __init__(self, max_size: int = 1000) -> None:
        self._max = max_size
        self._data: OrderedDict[str, _Entry] = OrderedDict()

    async def get(self, key: str) -> ChatCompletionResponse | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._data.pop(key, None)
            return None
        # LRU bump
        self._data.move_to_end(key)
        return entry.value

    async def set(self, key: str, value: ChatCompletionResponse, *, ttl: int) -> None:
        self._data[key] = _Entry(value=value, expires_at=time.time() + ttl)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


class SemanticCache:
    """Embedding-based nearest-neighbor cache.

    Stores `(embedding, response, expires_at)` tuples partitioned by model id.
    Lookup is O(N) over the partition — fine up to a few thousand entries.
    For larger working sets, swap the inner list for an ANN index (Faiss,
    pgvector). Public surface stays the same.
    """

    def __init__(self, *, threshold: float = 0.95, max_entries: int = 1000) -> None:
        self._threshold = threshold
        self._max = max_entries
        # namespace -> list of entries (most-recent last)
        self._partitions: dict[str, list[_Entry]] = {}
        # Exact-key index for `get(key)` fast path (some callers still use it).
        self._by_key: dict[str, _Entry] = {}

    def _evict_expired(self, partition: list[_Entry]) -> None:
        now = time.time()
        partition[:] = [e for e in partition if e.expires_at >= now]

    async def get(self, key: str) -> ChatCompletionResponse | None:
        """Exact-key fallback path. Used when the caller has the deterministic key."""
        entry = self._by_key.get(key)
        if entry is None or entry.expires_at < time.time():
            self._by_key.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: ChatCompletionResponse, *, ttl: int) -> None:
        """Exact-key set. Semantic stores go through `set_semantic` instead."""
        entry = _Entry(value=value, expires_at=time.time() + ttl)
        self._by_key[key] = entry

    async def get_semantic(
        self, *, namespace: str, text: str
    ) -> tuple[ChatCompletionResponse, float] | None:
        """Return (response, similarity) for the nearest neighbor over threshold, or None."""
        partition = self._partitions.get(namespace)
        if not partition:
            return None
        self._evict_expired(partition)
        if not partition:
            return None
        query = get_embedder().embed(text)
        best: _Entry | None = None
        best_sim = -1.0
        for entry in partition:
            if entry.embedding is None:
                continue
            sim = cosine(query, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best = entry
        if best is None or best_sim < self._threshold:
            return None
        return best.value, best_sim

    async def set_semantic(
        self,
        *,
        namespace: str,
        text: str,
        value: ChatCompletionResponse,
        ttl: int,
    ) -> None:
        embedding = get_embedder().embed(text)
        entry = _Entry(
            value=value,
            expires_at=time.time() + ttl,
            embedding=embedding,
            namespace=namespace,
            text=text,
        )
        partition = self._partitions.setdefault(namespace, [])
        partition.append(entry)
        # Trim oldest first if over capacity (FIFO is fine for a demo cache).
        while len(partition) > self._max:
            partition.pop(0)


_cache: CacheBackend | None = None


def get_cache() -> CacheBackend:
    global _cache
    if _cache is None:
        from src.core.config import get_settings

        s = get_settings()
        if s.semantic_cache_mode == "semantic":
            _cache = SemanticCache(
                threshold=s.semantic_cache_threshold,
                max_entries=s.semantic_cache_max_entries,
            )
        else:
            _cache = InMemoryCache(max_size=s.semantic_cache_max_entries)
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None
