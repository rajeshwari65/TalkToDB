"""Chunk policy documents, embed, and insert into policy_documents."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import POLICY_DIR
from backend.db import close_pool, get_pool
from backend.embeddings import embed_text, embedding_backend, to_pgvector


def chunk_document(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}\n\n{part}".strip() if buf else part
        if buf and len(candidate) > 700:
            chunks.append(buf)
            buf = part
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks or [text.strip()]


async def ingest() -> None:
    files = sorted(POLICY_DIR.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No policy documents in {POLICY_DIR}")
    print(f"Embedding backend: {embedding_backend()}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE policy_documents RESTART IDENTITY")
        total = 0
        for path in files:
            raw = path.read_text(encoding="utf-8")
            chunks = chunk_document(raw)
            for idx, chunk in enumerate(chunks, start=1):
                vec = to_pgvector(embed_text(chunk))
                await conn.execute(
                    """
                    INSERT INTO policy_documents (source_name, chunk_index, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4::vector)
                    """,
                    path.name,
                    idx,
                    chunk,
                    vec,
                )
                total += 1
                print(f"  ingested {path.name} chunk {idx} ({len(chunk)} chars)")
        count = await conn.fetchval("SELECT COUNT(*) FROM policy_documents")
        print(f"Done. {total} chunks written, table count={count}")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(ingest())
