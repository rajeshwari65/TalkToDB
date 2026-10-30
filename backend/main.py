"""FastAPI app: POST /query."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.catalog import load_catalog
from backend.db import close_pool, get_pool
from backend.fusion import fuse
from backend.llm import used_fallback
from backend.rag_retriever import retrieve
from backend.router import classify
from backend.sql_executor import execute_text_to_sql


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryResponse(BaseModel):
    answer: str
    mode: str
    sql_executed: str | None = None
    chunks_cited: list[dict] = Field(default_factory=list)
    confidence: float
    latency_ms: int
    sql_attempts: int | None = None
    fallback_llm: bool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(title="TalkToDB", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True, "fallback_llm": used_fallback()}


@app.get("/data")
async def data_catalog():
    try:
        return await load_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    t0 = time.perf_counter()
    question = req.question.strip()
    try:
        route = await classify(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sql_result = None
    chunks: list[dict] = []

    if route.mode in {"SQL_ONLY", "HYBRID"}:
        sql_q = route.sql_subquestion or question
        sql_result = await execute_text_to_sql(sql_q)

    if route.mode in {"DOCUMENT_ONLY", "HYBRID"}:
        doc_q = route.doc_subquestion or question
        chunks = await retrieve(doc_q)

    fused = await fuse(question, route.mode, sql_result, chunks)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_log
                    (question, routed_mode, sql_generated, sql_attempts, chunks_cited, confidence, latency_ms)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                """,
                question,
                route.mode,
                fused.get("sql_executed"),
                fused.get("sql_attempts") or 0,
                json.dumps(fused.get("chunks_cited") or []),
                fused.get("confidence"),
                latency_ms,
            )
    except Exception as exc:
        print(f"[query_log] failed: {exc}")

    return QueryResponse(
        answer=fused["answer"],
        mode=route.mode,
        sql_executed=fused.get("sql_executed"),
        chunks_cited=fused.get("chunks_cited") or [],
        confidence=fused["confidence"],
        latency_ms=latency_ms,
        sql_attempts=fused.get("sql_attempts"),
        fallback_llm=used_fallback(),
    )
