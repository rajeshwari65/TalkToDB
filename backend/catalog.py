"""Read-only snapshot of the demo tables and policy chunks."""

from __future__ import annotations

from backend.db import get_pool
from backend.sql_executor import rows_to_dicts


async def load_catalog() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        customers = rows_to_dicts(
            await conn.fetch("SELECT customer_id, name, email, signup_date FROM customers ORDER BY customer_id")
        )
        orders = rows_to_dicts(
            await conn.fetch(
                """
                SELECT o.order_id, o.customer_id, c.name AS customer_name,
                       o.order_date, o.amount, o.status
                FROM orders o
                JOIN customers c ON c.customer_id = o.customer_id
                ORDER BY o.order_date DESC, o.order_id
                """
            )
        )
        departments = rows_to_dicts(
            await conn.fetch("SELECT department_id, name FROM departments ORDER BY department_id")
        )
        revenue = rows_to_dicts(
            await conn.fetch(
                """
                SELECT r.revenue_id, r.department_id, d.name AS department,
                       r.quarter, r.amount
                FROM revenue r
                JOIN departments d ON d.department_id = r.department_id
                ORDER BY r.quarter, d.name
                """
            )
        )
        policies = rows_to_dicts(
            await conn.fetch(
                """
                SELECT doc_id, source_name, chunk_index, chunk_text
                FROM policy_documents
                ORDER BY source_name, chunk_index
                """
            )
        )
        spend = rows_to_dicts(
            await conn.fetch(
                """
                SELECT c.customer_id, c.name,
                       COALESCE(SUM(o.amount), 0) AS total_spent,
                       COUNT(o.order_id) AS order_count
                FROM customers c
                LEFT JOIN orders o
                  ON o.customer_id = c.customer_id
                 AND o.order_date >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY c.customer_id, c.name
                ORDER BY total_spent DESC
                """
            )
        )
        status_rows = rows_to_dicts(
            await conn.fetch(
                """
                SELECT status, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total
                FROM orders
                GROUP BY status
                ORDER BY n DESC
                """
            )
        )
        logs = rows_to_dicts(
            await conn.fetch(
                """
                SELECT log_id, question, routed_mode, confidence, latency_ms, created_at
                FROM query_log
                ORDER BY log_id DESC
                LIMIT 25
                """
            )
        )

    return {
        "note": "Fictional sample data for the TalkToDB demo (not a real company).",
        "counts": {
            "customers": len(customers),
            "orders": len(orders),
            "departments": len(departments),
            "revenue_rows": len(revenue),
            "policy_chunks": len(policies),
        },
        "customers": customers,
        "orders": orders,
        "departments": departments,
        "revenue": revenue,
        "policies": policies,
        "spend_6m": spend,
        "order_status": status_rows,
        "query_log": logs,
    }
