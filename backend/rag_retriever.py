"""In-database pgvector similarity search."""

from __future__ import annotations

import re

from backend.config import TOP_K
from backend.db import get_pool
from backend.embeddings import embed_text, embedding_backend, to_pgvector

_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "what", "which", "who",
    "of", "for", "to", "in", "on", "and", "or", "our", "company", "s",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP}


def _lexical(query: str, text: str) -> float:
    q, t = _tokens(query), _tokens(text)
    if not q:
        return 0.0
    return len(q & t) / len(q)


def _filename_score(query: str, source: str) -> float:
    src = source.replace("_", " ").replace("-", " ").replace(".txt", "")
    return _lexical(query, src)


async def retrieve(question: str, top_k: int | None = None) -> list[dict]:
    k = top_k or TOP_K
    vec = to_pgvector(embed_text(question))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source_name, chunk_index, chunk_text,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM policy_documents
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vec,
            max(k * 2, k),
        )
    results = [
        {
            "source": r["source_name"],
            "chunk_index": int(r["chunk_index"]),
            "chunk_text": r["chunk_text"],
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]
    # Hash embeddings are weak on paraphrases; blend in lexical overlap.
    if embedding_backend() == "hash":
        for item in results:
            lex = _lexical(question, item["chunk_text"])
            fn = _filename_score(question, item["source"])
            item["similarity"] = round(
                0.2 * item["similarity"] + 0.4 * lex + 0.4 * fn, 4
            )
        results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:k]
