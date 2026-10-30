"""Groq LLM wrapper with a heuristic fallback when no API key is present."""

from __future__ import annotations

import json
import re
from datetime import date

from backend.config import GROQ_API_KEY, GROQ_MODEL, groq_configured

_client = None
USED_FALLBACK = False


def last_completed_quarter(today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    q = (today.month - 1) // 3 + 1
    if q == 1:
        last_q, last_y = 4, today.year - 1
    else:
        last_q, last_y = q - 1, today.year
    current = f"{today.year}-Q{q}"
    last = f"{last_y}-Q{last_q}"
    return current, last


def _get_client():
    global _client
    if _client is None:
        from groq import AsyncGroq

        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json|sql)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def used_fallback() -> bool:
    return USED_FALLBACK


async def complete(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.0,
    question: str | None = None,
) -> str:
    """Call Groq. If unconfigured, use the local fallback so the rest of the stack still runs."""
    global USED_FALLBACK
    if groq_configured():
        try:
            client = _get_client()
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            kwargs: dict = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "").strip()
            return _strip_fences(content)
        except Exception as exc:
            print(f"[llm] Groq call failed ({type(exc).__name__}): {exc}")
            USED_FALLBACK = True
            return fallback_complete(prompt, json_mode=json_mode, question=question)
    USED_FALLBACK = True
    return fallback_complete(prompt, json_mode=json_mode, question=question)


def fallback_complete(
    prompt: str, *, json_mode: bool = False, question: str | None = None
) -> str:
    """Deterministic stand-in for the three canonical questions plus generic routing."""
    lower = prompt.lower()
    qtext = (question or _extract_user_question(prompt)).strip()

    if json_mode or "classify the user question" in lower:
        return json.dumps(_fallback_route(qtext))

    if "write a corrected single select" in lower or "fixing a postgresql" in lower:
        return _fallback_sql(qtext)

    if "output only the sql" in lower or "postgresql expert" in lower:
        return _fallback_sql(qtext)

    if "do not answer them separately" in lower or "qualifying entities" in lower:
        return _fallback_fusion(prompt)

    if "retrieved policy document chunks" in lower or "retrieved chunks:" in lower:
        return _fallback_rag(prompt)

    if "explain these postgresql query results" in lower:
        return _fallback_sql_explain(prompt)

    return "I could not reach the language model. Using retrieved context as-is."


def _extract_user_question(prompt: str) -> str:
    lower = prompt.lower()
    for marker in ("user question:", "original question:", "\nquestion:"):
        idx = lower.rfind(marker)
        if idx != -1:
            part = prompt[idx + len(marker) :]
            return part.strip().split("\n", 1)[0].strip()
    return prompt.strip()


def _fallback_route(question: str) -> dict:
    q = question.lower()
    # Canonical examples from the PRD.
    if "eligible for refund" in q and "spend" in q:
        return {
            "mode": "HYBRID",
            "sql_subquestion": "What is each customer's total spend in the last 6 months, including order dates and statuses?",
            "doc_subquestion": "What is the refund eligibility policy?",
        }
    if "highest revenue last quarter" in q or ("highest revenue" in q and "quarter" in q):
        return {
            "mode": "SQL_ONLY",
            "sql_subquestion": "Which department had the highest revenue last quarter?",
            "doc_subquestion": None,
        }
    if "refund policy" in q and "spend" not in q and "customer" not in q:
        return {
            "mode": "DOCUMENT_ONLY",
            "sql_subquestion": None,
            "doc_subquestion": "What is the company's refund policy?",
        }

    sql_hints = any(
        w in q
        for w in (
            "revenue",
            "order",
            "customer",
            "spend",
            "department",
            "how much",
            "highest",
            "total",
            "sales",
        )
    )
    doc_hints = any(
        w in q
        for w in (
            "policy",
            "refund",
            "shipping",
            "return",
            "eligible",
            "terms",
        )
    )
    if sql_hints and doc_hints:
        return {
            "mode": "HYBRID",
            "sql_subquestion": q,
            "doc_subquestion": q,
        }
    if doc_hints and not sql_hints:
        return {
            "mode": "DOCUMENT_ONLY",
            "sql_subquestion": None,
            "doc_subquestion": q,
        }
    if sql_hints:
        return {
            "mode": "SQL_ONLY",
            "sql_subquestion": q,
            "doc_subquestion": None,
        }
    return {
        "mode": "HYBRID",
        "sql_subquestion": q,
        "doc_subquestion": q,
    }


def _fallback_sql(question: str) -> str:
    q = question.lower()
    _, last_q = last_completed_quarter()
    if "highest revenue" in q or "last quarter" in q and "department" in q:
        return f"""
SELECT d.name AS department, r.quarter, r.amount
FROM revenue r
JOIN departments d ON d.department_id = r.department_id
WHERE r.quarter = '{last_q}'
ORDER BY r.amount DESC
LIMIT 1
""".strip()
    # Hybrid / spend questions: raw facts including dates and statuses.
    return """
SELECT c.customer_id,
       c.name,
       SUM(o.amount) AS total_spent_6m,
       json_agg(
         json_build_object(
           'order_id', o.order_id,
           'order_date', o.order_date,
           'amount', o.amount,
           'status', o.status
         )
         ORDER BY o.order_date DESC
       ) AS orders
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.order_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY c.customer_id, c.name
HAVING SUM(o.amount) > 0
ORDER BY total_spent_6m DESC
""".strip()


def _fallback_sql_explain(prompt: str) -> str:
    rows_blob = prompt.split("Rows (JSON):", 1)[-1].strip() if "Rows (JSON):" in prompt else "[]"
    try:
        rows = json.loads(rows_blob)
    except json.JSONDecodeError:
        return "The query ran but I could not parse the result rows."
    if not rows:
        return "The query returned no rows."
    top = rows[0]
    if "department" in top and "amount" in top:
        return (
            f"{top.get('department')} had the highest revenue in {top.get('quarter', 'the last quarter')} "
            f"at {top.get('amount')}."
        )
    return "Query results: " + json.dumps(rows, default=str)


def _fallback_rag(prompt: str) -> str:
    chunks = prompt.split("Retrieved chunks:", 1)[-1].strip()
    source = "the policy documents"
    match = re.search(r"source=(\S+)", chunks)
    if match:
        source = match.group(1)
    cleaned = re.sub(r"- source=\S+ chunk_index=\S+ similarity=\S+\n", "", chunks)
    snippet = cleaned[:1100].strip()
    return (
        f"According to {source}:\n\n{snippet}\n\n"
        f"Citation: {source}"
    )


def _fallback_fusion(prompt: str) -> str:
    """Apply the 30-day / not-pending / not-refunded rule when SQL JSON is present."""
    from datetime import datetime, timedelta

    rows_blob = prompt.split("SQL rows (JSON):", 1)[-1].strip() if "SQL rows (JSON):" in prompt else "[]"
    try:
        rows = json.loads(rows_blob)
    except json.JSONDecodeError:
        rows = []

    today = date.today()
    cutoff = today - timedelta(days=30)
    eligible = []
    for row in rows:
        orders = row.get("orders") or []
        if isinstance(orders, str):
            try:
                orders = json.loads(orders)
            except json.JSONDecodeError:
                orders = []
        qualifies = False
        for order in orders:
            status = str(order.get("status", "")).lower()
            raw_date = order.get("order_date")
            try:
                od = datetime.fromisoformat(str(raw_date)).date()
            except (TypeError, ValueError):
                continue
            if status == "completed" and od >= cutoff:
                qualifies = True
                break
        if qualifies:
            eligible.append(row)

    names = []
    for row in eligible:
        spent = row.get("total_spent_6m", row.get("total_spent"))
        names.append(f"{row.get('name', 'Unknown')} (${spent})")

    if not names:
        return (
            "Applying the Refund Policy (Refund_Policy_2026.txt) — full refunds require a request "
            "within 30 days of order_date, and the order must be completed (not pending, not already "
            "refunded) — none of the SQL rows currently qualify. SQL spend figures were retrieved "
            "but no customer has a completed order inside the 30-day window."
        )

    listed = "; ".join(names)
    return (
        f"Under the Refund Policy (Refund_Policy_2026.txt), customers are eligible for a full refund "
        f"only if they have a completed (not pending, not already refunded) order within 30 days of "
        f"{today.isoformat()}. Combining that rule with last-6-month spend from the orders table, "
        f"the qualifying customers and their totals are: {listed}."
    )
