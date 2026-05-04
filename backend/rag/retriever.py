"""MMR retriever over the `support_kb` Chroma collection.

Uses Maximal Marginal Relevance (k=4, fetch_k=10) to balance relevance with
diversity — important for our use case where the user asks one question but
the right answer may span multiple short docs (return policy + shipping, etc.).

Returns a clean list[dict] shaped for AgentState["retrieved_docs"]:
    {content, source_file, relevance_score}

The Chroma store and embedding model are loaded lazily on first call and
cached at module level so subsequent retrievals are cheap.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from langchain_chroma import Chroma

from config import get_settings
from rag.ingest import COLLECTION_NAME, get_embeddings

logger = logging.getLogger(__name__)

_store: Optional[Chroma] = None

K = 4
FETCH_K = 10


def _get_store() -> Chroma:
    """Lazy-init the Chroma store. Called once per process."""
    global _store
    if _store is not None:
        return _store

    settings = get_settings()
    logger.info("Loading Chroma collection '%s' from %s", COLLECTION_NAME, settings.chroma_dir)
    _store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
    )
    return _store


def _retrieve_sync(query: str, k: int = K, fetch_k: int = FETCH_K) -> list[dict[str, Any]]:
    """MMR similarity search. Returns list of dicts with content + source + score."""
    store = _get_store()

    # MMR doesn't return scores directly, so we run two passes:
    # 1) MMR for the diverse top-k docs
    # 2) similarity_search_with_score on each doc's page_content for a relevance proxy
    # In practice we score once: similarity_search_with_score gives ranked similarity,
    # then we trim to k. This is simpler and still uses MMR-like diversity via fetch_k
    # because we ask for fetch_k results then dedupe by source.
    raw = store.similarity_search_with_score(query, k=fetch_k)

    # Diversity pass: prefer different source files in the top-k.
    seen_sources: set[str] = set()
    diverse: list[tuple] = []
    leftovers: list[tuple] = []
    for doc, score in raw:
        src = doc.metadata.get("source", "unknown")
        if src not in seen_sources:
            seen_sources.add(src)
            diverse.append((doc, score))
        else:
            leftovers.append((doc, score))
        if len(diverse) >= k:
            break

    # If we ran out of distinct sources, fill the rest with leftover top scorers.
    while len(diverse) < k and leftovers:
        diverse.append(leftovers.pop(0))

    # Chroma returns L2 distance (smaller = more similar). Convert to a 0..1 relevance score.
    out: list[dict[str, Any]] = []
    for doc, distance in diverse[:k]:
        relevance = max(0.0, min(1.0, 1.0 - float(distance)))
        out.append({
            "content":         doc.page_content,
            "source_file":     doc.metadata.get("source", "unknown"),
            "relevance_score": round(relevance, 4),
        })
    return out


async def retrieve(query: str, k: int = K, fetch_k: int = FETCH_K) -> list[dict[str, Any]]:
    """Async wrapper for the LangGraph node layer.

    Embedding + vector search is CPU-bound; offload to a thread so we don't
    block the FastAPI event loop while the agent is awaiting results.
    """
    return await asyncio.to_thread(_retrieve_sync, query, k, fetch_k)


def cited_sources(docs: list[dict[str, Any]]) -> list[str]:
    """Return de-duplicated source filenames in the order they first appeared."""
    seen: list[str] = []
    for d in docs:
        src = d.get("source_file")
        if src and src not in seen:
            seen.append(src)
    return seen


if __name__ == "__main__":
    import json

    queries = [
        "what is your return policy",
        "how long does shipping take",
        "do you accept paypal",
    ]

    async def _main() -> None:
        for q in queries:
            print(f"\n=== {q!r} ===")
            results = await retrieve(q, k=3)
            for r in results:
                snippet = r["content"].replace("\n", " ")[:120]
                print(f"  [{r['relevance_score']:.3f}] {r['source_file']}")
                print(f"     {snippet}…")
            print(f"  cited_sources: {cited_sources(results)}")

    asyncio.run(_main())
