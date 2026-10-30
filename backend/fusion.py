"""Mode-specific answers, confidence scores, and hybrid fusion."""

from __future__ import annotations

import json
from datetime import date

from backend.config import load_prompt
from backend.llm import complete

CAVEAT = (
    "Caveat: confidence is below 0.5, so this answer may be incomplete or wrong. "
    "Treat it as a starting point, not a certain result."
)


def sql_confidence(attempts: int, empty: bool) -> float:
    if empty:
        return 0.2
    if attempts <= 1:
        return 0.9
    if attempts == 2:
        return 0.7
    return 0.5


def doc_confidence(chunks: list[dict]) -> float:
    if not chunks:
        return 0.2
    scores = [float(c.get("similarity") or 0.0) for c in chunks]
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def hybrid_confidence(sql_score: float, doc_score: float) -> float:
    return round((sql_score + doc_score) / 2.0, 3)


def _maybe_caveat(answer: str, confidence: float) -> str:
    if confidence < 0.5 and CAVEAT.lower() not in answer.lower():
        return f"{answer}\n\n{CAVEAT}"
    return answer


def _format_chunks(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        sim = c.get("similarity")
        sim_s = f"{sim:.3f}" if isinstance(sim, (int, float)) else "n/a"
        blocks.append(
            f"- source={c.get('source')} chunk_index={c.get('chunk_index')} "
            f"similarity={sim_s}\n{c.get('chunk_text', '')}"
        )
    return "\n\n".join(blocks) if blocks else "(no chunks retrieved)"


def cited_from(chunks: list[dict]) -> list[dict]:
    return [
        {
            "source": c.get("source"),
            "chunk_index": c.get("chunk_index"),
            "similarity": round(float(c.get("similarity") or 0.0), 4),
        }
        for c in chunks
    ]


async def answer_sql(question: str, sql_result: dict) -> str:
    rows = sql_result.get("rows") or []
    sql = sql_result.get("sql") or ""
    if sql_result.get("empty") and not rows:
        err = sql_result.get("error") or "The query returned no rows."
        return (
            f"I could not produce a reliable SQL answer after "
            f"{sql_result.get('attempts', 3)} attempt(s). Last query:\n{sql}\n\n{err}"
        )
    prompt = (
        "Explain these PostgreSQL query results in plain language for a business user. "
        "Do not invent numbers. If there is a clear winner (e.g. highest revenue), name it.\n\n"
        f"Question: {question}\n\nSQL:\n{sql}\n\nRows (JSON):\n"
        f"{json.dumps(rows, default=str)}"
    )
    return await complete(prompt, temperature=0.0, question=question)


async def answer_docs(question: str, chunks: list[dict]) -> str:
    prompt = load_prompt("rag_answer_prompt.txt").format(
        question=question,
        chunks=_format_chunks(chunks),
    )
    return await complete(prompt, temperature=0.0, question=question)


async def answer_hybrid(question: str, sql_result: dict, chunks: list[dict]) -> str:
    prompt = load_prompt("fusion_prompt.txt").format(
        today=date.today().isoformat(),
        question=question,
        chunks=_format_chunks(chunks),
        sql=sql_result.get("sql") or "",
        sql_rows=json.dumps(sql_result.get("rows") or [], default=str),
    )
    return await complete(prompt, temperature=0.0, question=question)


async def fuse(
    question: str,
    mode: str,
    sql_result: dict | None,
    chunks: list[dict],
) -> dict:
    sql_result = sql_result or {
        "sql": None,
        "rows": [],
        "attempts": 0,
        "error": None,
        "empty": True,
    }
    sql_score = sql_confidence(sql_result.get("attempts") or 1, bool(sql_result.get("empty")))
    doc_score = doc_confidence(chunks)

    if mode == "SQL_ONLY":
        confidence = sql_score
        answer = await answer_sql(question, sql_result)
        cited: list[dict] = []
    elif mode == "DOCUMENT_ONLY":
        confidence = doc_score
        answer = await answer_docs(question, chunks)
        cited = cited_from(chunks)
    else:
        confidence = hybrid_confidence(sql_score, doc_score)
        answer = await answer_hybrid(question, sql_result, chunks)
        cited = cited_from(chunks)

    confidence = round(float(confidence), 3)
    return {
        "answer": _maybe_caveat(answer, confidence),
        "confidence": confidence,
        "chunks_cited": cited,
        "sql_executed": sql_result.get("sql"),
        "sql_attempts": sql_result.get("attempts") or 0,
    }
