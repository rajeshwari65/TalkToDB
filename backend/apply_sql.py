"""Apply schema.sql then seed.sql."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python backend/apply_sql.py` as well as `python -m backend.apply_sql`.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import SQL_DIR
from backend.db import close_pool, get_pool


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


async def apply() -> None:
    pool = await get_pool()
    schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    seed = (SQL_DIR / "seed.sql").read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        for stmt in _split_sql(schema) + _split_sql(seed):
            await conn.execute(stmt)
        counts = {
            "customers": await conn.fetchval("SELECT COUNT(*) FROM customers"),
            "orders": await conn.fetchval("SELECT COUNT(*) FROM orders"),
            "departments": await conn.fetchval("SELECT COUNT(*) FROM departments"),
            "revenue": await conn.fetchval("SELECT COUNT(*) FROM revenue"),
        }
        q3 = await conn.fetch(
            """
            SELECT d.name, r.amount
            FROM revenue r
            JOIN departments d ON d.department_id = r.department_id
            WHERE r.quarter = '2026-Q3'
            ORDER BY r.amount DESC
            """
        )
        print("Applied schema + seed.")
        print("Counts:", counts)
        print("2026-Q3 revenue (desc):", [dict(r) for r in q3])
    await close_pool()


if __name__ == "__main__":
    asyncio.run(apply())
