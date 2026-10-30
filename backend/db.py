"""Async Postgres connection pool (Supabase or local pgvector)."""

from __future__ import annotations

import ssl as ssl_mod
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import asyncpg

from backend.config import DATABASE_URL

_pool: asyncpg.Pool | None = None


def _ssl_context(sslmode: str, host: str):
    """Match libpq: require = encrypt without CA verify (Windows+Supabase often needs this)."""
    needs_ssl = sslmode in {"require", "verify-ca", "verify-full"} or "supabase.co" in host
    if not needs_ssl:
        return None
    ctx = ssl_mod.create_default_context()
    if sslmode in {"verify-ca", "verify-full"}:
        return ctx
    ctx.check_hostname = False
    ctx.verify_mode = ssl_mod.CERT_NONE
    return ctx


def normalize_dsn(url: str) -> tuple[str, object | None]:
    """asyncpg does not honor libpq sslmode; peel it off and set ssl separately."""
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env or use docker-compose."
        )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    sslmode = (qs.pop("sslmode", ["prefer"])[0] or "prefer").lower()
    new_query = urlencode({k: v[0] if len(v) == 1 else v for k, v in qs.items()})
    dsn = urlunparse(parsed._replace(query=new_query))
    host = (parsed.hostname or "").lower()
    return dsn, _ssl_context(sslmode, host)


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.execute("SET statement_timeout = '15000'")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn, ssl_ctx = normalize_dsn(DATABASE_URL)
        kwargs: dict = {
            "dsn": dsn,
            "min_size": 1,
            "max_size": 5,
            "init": _init_connection,
            "command_timeout": 20,
        }
        if ssl_ctx is not None:
            kwargs["ssl"] = ssl_ctx
        _pool = await asyncpg.create_pool(**kwargs)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
