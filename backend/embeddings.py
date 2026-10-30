"""Local embeddings: sentence-transformers, with a hashed fallback if the model isn't available."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from backend.config import EMBEDDING_MODEL

_model = None
_backend = "unset"


def _hash_embed(text: str) -> list[float]:
    """Token-hash bag-of-words into 768 dims so similar wording still overlaps."""
    vec = np.zeros(768, dtype=np.float32)
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        a = int.from_bytes(digest[:8], "little")
        b = int.from_bytes(digest[8:16], "little")
        vec[a % 768] += 1.0
        vec[b % 768] += 0.5
    norm = float(np.linalg.norm(vec))
    if norm:
        vec /= norm
    return vec.tolist()


def _load_model():
    global _model, _backend
    if _backend != "unset":
        return
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
        _backend = "sentence-transformers"
    except Exception:
        _model = None
        _backend = "hash"


def embedding_backend() -> str:
    _load_model()
    return _backend


def embed_text(text: str) -> list[float]:
    _load_model()
    if _model is None:
        return _hash_embed(text)
    vec = _model.encode(text, normalize_embeddings=True)
    return [float(x) for x in vec.tolist()]


def embed_texts(texts: list[str]) -> list[list[float]]:
    _load_model()
    if _model is None:
        return [_hash_embed(t) for t in texts]
    mat = _model.encode(texts, normalize_embeddings=True)
    return [[float(x) for x in row.tolist()] for row in mat]


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
