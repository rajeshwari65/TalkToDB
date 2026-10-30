# TalkToDB v2 — Implementation Plan

Phase A (understand) and Phase B (plan) are recorded here. Phase C proceeds immediately.

## Locked decisions

- Three modes: SQL_ONLY, DOCUMENT_ONLY, HYBRID. HYBRID = decompose + retrieve/query + fuse into one cited answer (not two concatenated answers).
- Stack: Supabase Postgres + pgvector, Groq Llama 3.3 70B, local `all-mpnet-base-v2` embeddings, FastAPI, React+Vite.
- Stack: Postgres + pgvector, Groq Llama 3.3 70B, local embeddings, FastAPI, React+Vite.
- Section 9 rules are required: JSON router (+1 retry), SQL max_attempts=3, SELECT-only guard, confidence formulas, caveat if confidence < 0.5, fusion prompt that intersects policy with SQL rows.
- Driver: asyncpg. Ingest is a CLI (`python -m backend.ingest`), not an HTTP endpoint.
- Hybrid SQL returns raw facts (spend, order dates, statuses); fusion applies policy.
- If `DATABASE_URL` is missing, local Docker pgvector on port 54329 is the workaround.
- If `GROQ_API_KEY` is missing, a heuristic fallback LLM is used so E2E tests can still run; Groq remains the primary path.

## Build order

1. Scaffold + db.py
2. schema.sql + seed.sql + apply_sql.py
3. embeddings.py + llm.py
4. policy docs + ingest.py
5. rag_retriever.py + sql_executor.py + router.py
6. fusion.py + main.py
7. React chat UI
8. curl the three canonical questions
