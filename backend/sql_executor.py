"""Text-to-SQL with a bounded self-correction loop and SELECT-only safety."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal

from backend.config import load_prompt
from backend.db import get_pool
from backend.llm import complete, last_completed_quarter

MAX_ATTEMPTS = 3
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|MERGE|GRANT|REVOKE|COPY|CALL)\b",
    re.IGNORECASE,
)


def _quarters() -> tuple[str, str, str]:
    today = date.today()
    current, last = last_completed_quarter(today)
    return today.isoformat(), current, last


def is_safe_select(sql: str) -> bool:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        return False
    if ";" in cleaned:
        return False
    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE | re.DOTALL):
        return False
    if FORBIDDEN.search(cleaned):
        return False
    return True


def _jsonify(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, memoryview):
        return bytes(value).decode("utf-8", errors="replace")
    return value


def rows_to_dicts(records) -> list[dict]:
    out = []
    for rec in records:
        row = {}
        for k, v in dict(rec).items():
            if isinstance(v, str) and v[:1] in "[{":
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    pass
            row[k] = _jsonify(v)
        out.append(row)
    return out


def extract_sql(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    # If the model added commentary, take from the first SELECT.
    match = re.search(r"\bSELECT\b", text, re.I)
    if match:
        text = text[match.start() :]
    return text.strip().rstrip(";").strip()


async def generate_sql(question: str) -> str:
    today, current, last = _quarters()
    prompt = load_prompt("sql_gen_prompt.txt").format(
        today=today,
        current_quarter=current,
        last_quarter=last,
        question=question,
    )
    raw = await complete(prompt, temperature=0.0, question=question)
    return extract_sql(raw)


async def fix_sql(question: str, sql: str, feedback: str) -> str:
    today, _, last = _quarters()
    prompt = load_prompt("sql_fix_prompt.txt").format(
        today=today,
        last_quarter=last,
        question=question,
        sql=sql,
        feedback=feedback,
    )
    raw = await complete(prompt, temperature=0.0, question=question)
    return extract_sql(raw)


async def run_select(sql: str) -> list[dict]:
    if not is_safe_select(sql):
        raise PermissionError(f"Rejected non-SELECT or unsafe SQL: {sql}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(sql)
    return rows_to_dicts(records)


async def execute_text_to_sql(question: str) -> dict:
    """Return {sql, rows, attempts, error, empty} after up to MAX_ATTEMPTS."""
    sql = ""
    rows: list[dict] = []
    last_error = None
    attempts = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts = attempt
        try:
            if attempt == 1:
                sql = await generate_sql(question)
            else:
                sql = await fix_sql(question, sql, last_error or "")

            if not is_safe_select(sql):
                last_error = (
                    f"The query was rejected by the SELECT-only safety filter. "
                    f"Rejected SQL:\n{sql}\nWrite a single SELECT with no DML/DDL."
                )
                print(f"[sql_executor] rejected unsafe SQL on attempt {attempt}: {sql!r}")
                continue

            rows = await run_select(sql)
            if rows:
                return {
                    "sql": sql,
                    "rows": rows,
                    "attempts": attempts,
                    "error": None,
                    "empty": False,
                }
            last_error = (
                "The query ran successfully but returned zero rows. "
                "Reconsider filters, joins, casing of status/quarter values, "
                f"and date windows. Failed SQL:\n{sql}"
            )
        except PermissionError as exc:
            last_error = str(exc)
            print(f"[sql_executor] {exc}")
        except Exception as exc:
            last_error = (
                f"Postgres error:\n{type(exc).__name__}: {exc}\n"
                f"Failed SQL:\n{sql}\n"
                "Fix the SQL for PostgreSQL."
            )

    return {
        "sql": sql,
        "rows": rows,
        "attempts": attempts,
        "error": last_error,
        "empty": True,
    }
