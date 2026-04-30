"""
Vector Store
Manages per-company FAISS indexes with persistence.
Supports OpenAI and Gemini embeddings.
"""

import os
import json
import logging
import pickle
import numpy as np
import faiss
from app.config import (
    EMBEDDING_PROVIDER, EMBEDDING_MODEL,
    OPENAI_API_KEY, GEMINI_API_KEY,
    VECTOR_STORE_PATH
)

logger = logging.getLogger(__name__)

os.makedirs(VECTOR_STORE_PATH, exist_ok=True)


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _get_embeddings(texts: list[str]) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "gemini":
        return _gemini_embed(texts)
    return _openai_embed(texts)


def _openai_embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    # Batch in groups of 100 to stay within API limits
    all_embeddings = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i+100]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([e.embedding for e in resp.data])
    return all_embeddings


def _gemini_embed(texts: list[str]) -> list[list[float]]:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    embeddings = []
    for text in texts:
        # Truncate to avoid token limit issues
        truncated = text[:8000]
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=truncated
        )
        embeddings.append(result["embedding"])
    return embeddings


# ---------------------------------------------------------------------------
# Index paths
# ---------------------------------------------------------------------------

def _safe_name(company: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in company).lower()


def _index_path(company: str) -> str:
    return os.path.join(VECTOR_STORE_PATH, f"{_safe_name(company)}.faiss")


def _meta_path(company: str) -> str:
    return os.path.join(VECTOR_STORE_PATH, f"{_safe_name(company)}_meta.pkl")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_exists(company: str) -> bool:
    return os.path.exists(_index_path(company)) and os.path.exists(_meta_path(company))


def build_index(company: str, chunks: list[dict]) -> None:
    """Embed chunks and save FAISS index + metadata to disk."""
    texts = [c["text"] for c in chunks]
    metadata = [c["metadata"] for c in chunks]

    logger.info(f"Embedding {len(texts)} chunks for '{company}'...")
    embeddings = _get_embeddings(texts)

    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    vectors = np.array(embeddings, dtype=np.float32)
    index.add(vectors)

    faiss.write_index(index, _index_path(company))
    with open(_meta_path(company), "wb") as f:
        pickle.dump({"texts": texts, "metadata": metadata}, f)

    logger.info(f"Index saved for '{company}': {len(texts)} chunks, dim={dim}")


def load_index(company: str) -> tuple:
    """Load FAISS index and metadata. Returns (index, texts, metadata)."""
    try:
        index = faiss.read_index(_index_path(company))
        with open(_meta_path(company), "rb") as f:
            data = pickle.load(f)
        return index, data["texts"], data["metadata"]
    except Exception as e:
        logger.error(f"Failed to load index for '{company}': {e}")
        # Delete corrupted files and signal re-ingestion needed
        for path in [_index_path(company), _meta_path(company)]:
            if os.path.exists(path):
                os.remove(path)
        raise


def search(company: str, query: str, top_k: int = 6) -> list[dict]:
    """
    Embed query and retrieve top_k chunks.
    Returns list of { text, metadata, score }
    """
    index, texts, metadata = load_index(company)

    query_vec = np.array(_get_embeddings([query]), dtype=np.float32)
    distances, indices = index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        results.append({
            "text": texts[idx],
            "metadata": metadata[idx],
            "score": float(dist)
        })

    return results
