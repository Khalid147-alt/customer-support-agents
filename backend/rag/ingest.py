"""Ingest /docs/ into ChromaDB.

Loads every .txt file under DOCS_DIR, chunks (500/50), embeds with
HuggingFace `all-MiniLM-L6-v2` (free, no API key, runs locally), and
persists to a Chroma collection named `support_kb`.

Idempotent: clears and rebuilds the collection on each run so doc edits
take effect cleanly. Run with:

    python -m rag.ingest
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("ingest")

# Docs live under backend/docs/ so they're reachable from inside the Docker
# image (which has backend/ as its build context). The repo also keeps a copy
# at the repo root for browseability, but ingestion always reads the
# backend-local copy.
BACKEND_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BACKEND_DIR / "docs"

COLLECTION_NAME = "support_kb"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def get_embeddings() -> HuggingFaceEmbeddings:
    """Lazy embedding-model loader. First call downloads ~90 MB to ~/.cache/huggingface."""
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        # cpu so this runs identically on dev laptops and Railway boxes.
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def load_docs(docs_dir: Path) -> list:
    """Load every .txt under docs_dir as LangChain Documents with source metadata."""
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs directory not found: {docs_dir}")

    loader = DirectoryLoader(
        str(docs_dir),
        glob="*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
    )
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No .txt documents found in {docs_dir}")

    # Normalize the `source` metadata to just the filename — easier to display in citation pills.
    for d in docs:
        full = d.metadata.get("source", "")
        d.metadata["source"] = Path(full).name if full else "unknown"

    logger.info("Loaded %d documents from %s", len(docs), docs_dir)
    return docs


def chunk_docs(docs: list) -> list:
    """Split into ~500-char chunks with 50-char overlap. Preserves metadata per chunk."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info("Split %d docs into %d chunks", len(docs), len(chunks))
    return chunks


def ingest(persist_dir: str | Path) -> Chroma:
    """End-to-end: load → chunk → embed → persist. Returns the populated Chroma store."""
    persist_dir = str(persist_dir)

    docs = load_docs(DOCS_DIR)
    chunks = chunk_docs(docs)
    embeddings = get_embeddings()

    # Wipe any prior collection so re-runs reflect the latest /docs/ state cleanly.
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    try:
        store.delete_collection()
        logger.info("Cleared existing collection '%s'", COLLECTION_NAME)
    except Exception as exc:  # noqa: BLE001 — best-effort wipe; safe to ignore on first run
        logger.debug("No existing collection to clear (%s)", exc)

    store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )
    logger.info(
        "Persisted %d chunks to Chroma collection '%s' at %s",
        len(chunks), COLLECTION_NAME, persist_dir,
    )
    return store


def ingest_docs() -> Chroma:
    """Ingest using the configured CHROMA_DIR. Used by the lifespan bootstrap."""
    return ingest(get_settings().chroma_dir)


def _smoke_query(store: Chroma, query: str) -> None:
    """Run a quick similarity search to prove ingestion worked."""
    print(f"\n=== similarity_search({query!r}, k=3) ===")
    results = store.similarity_search_with_score(query, k=3)
    for i, (doc, score) in enumerate(results, 1):
        snippet = doc.page_content.replace("\n", " ")[:140]
        print(f"  [{i}] score={score:.4f}  source={doc.metadata.get('source')}")
        print(f"      {snippet}…")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest KB docs into ChromaDB.")
    parser.add_argument(
        "--query",
        default="what is your return policy",
        help="Smoke-test query to run after ingestion.",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = ingest(settings.chroma_dir)
    _smoke_query(store, args.query)
    sys.exit(0)
