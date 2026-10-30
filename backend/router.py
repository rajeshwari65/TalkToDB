"""LLM question classifier / decomposer."""

from __future__ import annotations

import json
import re

from backend.config import load_prompt
from backend.llm import complete

VALID_MODES = {"SQL_ONLY", "DOCUMENT_ONLY", "HYBRID"}


class Route:
    def __init__(self, mode: str, sql_subquestion: str | None, doc_subquestion: str | None):
        self.mode = mode
        self.sql_subquestion = sql_subquestion
        self.doc_subquestion = doc_subquestion

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "sql_subquestion": self.sql_subquestion,
            "doc_subquestion": self.doc_subquestion,
        }


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize(data: dict) -> Route:
    mode = str(data.get("mode", "")).strip().upper().replace(" ", "_")
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    sql_q = data.get("sql_subquestion")
    doc_q = data.get("doc_subquestion")
    if isinstance(sql_q, str):
        sql_q = sql_q.strip() or None
    else:
        sql_q = None
    if isinstance(doc_q, str):
        doc_q = doc_q.strip() or None
    else:
        doc_q = None
    if mode == "SQL_ONLY":
        doc_q = None
    elif mode == "DOCUMENT_ONLY":
        sql_q = None
    elif mode == "HYBRID":
        if not sql_q or not doc_q:
            # Incomplete hybrid: still treat as hybrid; caller will fall back to original question.
            pass
    return Route(mode, sql_q, doc_q)


async def classify(question: str) -> Route:
    base = load_prompt("router_prompt.txt")
    prompt = f"{base}\n\nUser question:\n{question}"
    try:
        raw = await complete(prompt, json_mode=True, temperature=0.0, question=question)
        return _normalize(_extract_json(raw))
    except Exception:
        retry = (
            prompt
            + "\n\nYour previous reply was not valid JSON. "
            "Return ONLY valid JSON, no markdown fences, no extra text."
        )
        try:
            raw = await complete(retry, json_mode=True, temperature=0.0, question=question)
            return _normalize(_extract_json(raw))
        except Exception as exc:
            raise ValueError(f"Router failed to return valid JSON: {exc}") from exc
