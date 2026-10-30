# TalkToDB — Full system brief for a presentation deck

You are generating a PowerPoint for a student SQL / database project presentation. The project is called **TalkToDB**. This document is the source of truth. Do not invent features, tables, numbers, or technologies that are not written here. If something is listed as a limitation, present it honestly as a limitation, not as a finished feature.

Audience: classmates and a faculty evaluator who know SQL but may not know RAG, embeddings, or LLMs in depth. Explain those ideas in plain language, then show the technical detail. The project must come across as a **database project first**: schema design, seed data, SQL generation, query safety, and logging. The LLM and document search exist so a person can ask questions in English and still get answers grounded in PostgreSQL.

Tone: confident, concrete, demo-driven. Prefer diagrams, worked examples, and the three canonical questions. Avoid marketing language. Suggested length: 14–18 slides. Dark theme is optional; the app itself is a dark chat UI (background `#0f141c`, accent blue `#3b82f6`).

---

## 1. One-sentence pitch

TalkToDB is a hybrid question-answering system: a person types a natural-language question, the system decides whether the answer lives in PostgreSQL, in company policy documents stored as vectors, or in both, then returns one cited answer with a confidence score.

## 2. Problem this project solves

Business questions are not all the same shape.

- Some questions are pure facts in tables: “Which department had the highest revenue last quarter?”
- Some questions are rules written in documents: “What is the company’s refund policy?”
- Some questions need both: “Which customers are eligible for a refund, and how much did they spend in the last 6 months?” Eligibility is a written policy. Spend is a number in the `orders` table. Neither source alone is enough.

A normal SQL client forces the user to know the schema and write the query. A normal document chatbot cannot add up orders. TalkToDB routes the question, runs the right tool, and — when both are needed — applies the policy to the SQL rows instead of pasting two unrelated answers together.

## 3. What is actually built (version 2.0.0)

This is a working local application, not a slide-only design.

Built and wired end to end:

- PostgreSQL schema with relational tables plus a vector table (`pgvector`).
- Realistic seed data: 16 customers, 48 orders, 5 departments, 20 revenue rows (4 quarters × 5 departments). Dates are relative to `CURRENT_DATE`, so “last 30 days” and “last 6 months” stay correct whenever the demo is run.
- Three policy documents, chunked, embedded, and stored in Postgres.
- FastAPI backend with one main endpoint: `POST /query`.
- A router that classifies each question into `SQL_ONLY`, `DOCUMENT_ONLY`, or `HYBRID`, and splits a hybrid question into two sub-questions.
- A text-to-SQL engine that writes a single `SELECT`, refuses anything that is not a safe read, executes it, and retries up to 3 times if Postgres errors or the result is empty.
- A document retriever that embeds the question and does cosine similarity search inside Postgres (`pgvector`), returning the top 5 chunks.
- A fusion step that, for hybrid questions, intersects policy rules with SQL rows and produces one answer that cites both the numbers and the document filename.
- A confidence score with an explicit caveat when confidence is below 0.5.
- A `query_log` table that stores every question, the route, the SQL, attempts, cited chunks, confidence, and latency.
- A React chat UI with three example questions, mode badges, confidence meter, expandable SQL, and expandable citations.
- A heuristic fallback so the three demo questions still run if the Groq API key is missing. The real path is Groq.

Not built (do not claim these):

- User login, multi-tenant access, or row-level security.
- A general database the user can point at any schema. The schema is fixed and described in the SQL prompt.
- Voice, charts, or CSV export.
- Automatic re-ingest when a policy file changes. Ingest is a manual CLI command.
- Evaluation benchmarks or a formal accuracy score beyond the confidence heuristic.

## 4. Suggested slide outline

1. Title — TalkToDB: asking a database in English
2. The problem — three kinds of questions
3. What the system does — one question in, one cited answer out
4. Architecture — browser → FastAPI → router → SQL and/or RAG → fusion → Postgres
5. Tech stack — and why each piece was chosen
6. Relational schema — ER diagram of customers, orders, departments, revenue
7. The business data — what the seed is designed to prove
8. Policy documents — why they live in the same database as vectors
9. Request lifecycle — step by step for one question
10. Mode 1 demo — SQL only (highest revenue last quarter)
11. Text-to-SQL internals — prompt, safety filter, self-correction loop
12. Mode 2 demo — documents only (refund policy) and how retrieval works
13. Mode 3 demo — hybrid fusion (who is eligible, and their 6-month spend)
14. Confidence, citations, and the query log
15. The chat UI
16. How to run it
17. Limitations and what we would do next
18. Closing — the database is the system of record; the LLM only translates and explains

Speaker notes should be written under each slide in the deck notes, using the facts in sections 5–18 below.

---

## 5. Architecture (describe this as a diagram)

```
User (browser, React + Vite, http://localhost:5173)
        |
        | POST /query  { "question": "..." }
        | Vite proxies /query and /health to the API
        v
FastAPI  (uvicorn, http://127.0.0.1:8000)
        |
        | 1. Router LLM call
        |    returns JSON: mode + optional sql_subquestion + optional doc_subquestion
        |
        +-- if SQL_ONLY or HYBRID --> Text-to-SQL
        |       generate SELECT (Groq)
        |       safety check (SELECT only, no second statement, no DML/DDL)
        |       execute on Postgres via asyncpg
        |       if error or 0 rows: fix SQL and retry, max 3 attempts
        |
        +-- if DOCUMENT_ONLY or HYBRID --> RAG retriever
        |       embed the question locally (768-dim vector)
        |       cosine search in policy_documents (pgvector, HNSW index)
        |       return top 5 chunks with similarity scores
        |
        | 2. Fusion
        |    SQL_ONLY        -> explain the rows in plain language
        |    DOCUMENT_ONLY   -> answer only from chunks, cite filenames
        |    HYBRID          -> apply the policy to the SQL rows, one combined answer
        |
        | 3. Confidence + optional caveat if score < 0.5
        |
        | 4. INSERT into query_log
        v
JSON response:
  answer, mode, sql_executed, chunks_cited, confidence, latency_ms, sql_attempts
```

Important design rule for hybrid: SQL returns **raw facts** (who, how much, order dates, statuses). It does **not** encode the refund policy inside the SQL. The fusion model applies the policy afterward. That keeps the policy in the document, where it can change, instead of hard-coding “30 days” into every query.

There are two LLM calls on a simple question (route, then answer) and more on SQL (route, generate SQL, maybe fix SQL up to twice more, then explain). Temperature is 0.0 on every call so answers stay stable for a demo.

---

## 6. Tech stack — what we used and why

| Piece | What | Why it is in the project |
| --- | --- | --- |
| Database | PostgreSQL 16 | Relational data plus vectors in one database. Joins, dates, aggregates, and similarity search share one connection. |
| Vector extension | pgvector | Stores 768-dimensional embeddings and supports cosine distance (`<=>`) and an HNSW index. |
| Hosting options | Supabase (free tier) **or** local Docker | Supabase is the intended hosted Postgres. `docker compose` runs `pgvector/pgvector:pg16` on host port **54329** if there is no cloud database. |
| DB driver | asyncpg | Async connection pool (min 1, max 5). Statement timeout 15 seconds. Command timeout 20 seconds. |
| API | FastAPI + Uvicorn + Pydantic v2 | One typed endpoint. CORS limited to the Vite dev origin (`localhost:5173`). |
| LLM | Groq API, model `openai/gpt-oss-120b` | Fast hosted chat model. No local GPU required. **This is Groq, not xAI Grok.** An older plan mentioned Llama 3.3 70B; the code default is `openai/gpt-oss-120b`. |
| Embeddings | `sentence-transformers`, model `all-mpnet-base-v2` | Runs locally. 768 dimensions. Vectors are L2-normalized. No embedding API key and no per-query embedding cost. |
| Embedding fallback | hashed bag-of-words into 768 dims | Used only if the sentence-transformer model cannot load. Retrieval then blends vector score with word overlap. The intended demo path is the real model. |
| LLM fallback | keyword heuristics in `backend/llm.py` | Used only if `GROQ_API_KEY` is missing or the API call fails. It knows the three canonical demo questions. It is a safety net, not the product. |
| Frontend | React 18 + Vite 5 | Chat UI. No component library. Vite proxies `/query` and `/health` to port 8000 so the browser does not deal with CORS during development. |
| Config | python-dotenv, root `.env` | `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `EMBEDDING_MODEL`, `TOP_K` (default 5). |

Python dependencies (`backend/requirements.txt`): fastapi, uvicorn, asyncpg, python-dotenv, pydantic, groq, sentence-transformers, numpy.

---

## 7. Relational schema (this is the SQL core — give it a full ER slide)

All of this is in `sql/schema.sql`. The script drops and recreates tables, so it is safe to re-run in development. It also runs `CREATE EXTENSION IF NOT EXISTS vector`.

### customers
| Column | Type | Notes |
| --- | --- | --- |
| customer_id | SERIAL PK | |
| name | VARCHAR(200) | |
| email | VARCHAR(200) | |
| signup_date | DATE | |

### orders
| Column | Type | Notes |
| --- | --- | --- |
| order_id | SERIAL PK | |
| customer_id | INTEGER FK → customers | |
| order_date | DATE | |
| amount | NUMERIC(10,2) | |
| status | VARCHAR(50) | only three values in the seed: `completed`, `refunded`, `pending` |

### departments
| Column | Type | Notes |
| --- | --- | --- |
| department_id | SERIAL PK | |
| name | VARCHAR(100) | Sales, Marketing, Engineering, Support, Operations |

### revenue
| Column | Type | Notes |
| --- | --- | --- |
| revenue_id | SERIAL PK | |
| department_id | INTEGER FK → departments | |
| quarter | VARCHAR(10) | values like `2026-Q3` |
| amount | NUMERIC(12,2) | department revenue for that quarter, not order line items |

Relationships:

- One customer has many orders.
- One department has many revenue rows (one per quarter).
- `orders` and `revenue` are **not** joined to each other. Customer spend comes from `orders.amount`. Department performance comes from `revenue.amount`. Say this explicitly so the audience does not think order totals must equal department revenue. They are two different facts for two different questions.

### policy_documents (unstructured text, same database)
| Column | Type | Notes |
| --- | --- | --- |
| doc_id | SERIAL PK | |
| source_name | VARCHAR(200) | filename, e.g. `Refund_Policy_2026.txt` |
| chunk_index | INTEGER | 1-based chunk number inside that file |
| chunk_text | TEXT | the actual paragraph(s) |
| embedding | VECTOR(768) | cosine embedding of `chunk_text` |

Index:

```sql
CREATE INDEX policy_docs_hnsw_idx
    ON policy_documents
    USING hnsw (embedding vector_cosine_ops);
```

HNSW is an approximate nearest-neighbor index. The search orders by cosine distance. Similarity reported to the user is `1 - (embedding <=> query_vector)`.

### query_log (observability, also a real table)
| Column | Type | Notes |
| --- | --- | --- |
| log_id | SERIAL PK | |
| question | TEXT | the user’s original question |
| routed_mode | VARCHAR(20) | SQL_ONLY / DOCUMENT_ONLY / HYBRID |
| sql_generated | TEXT | the SELECT that ran, if any |
| sql_attempts | INTEGER | 1 to 3 |
| chunks_cited | JSONB | source, chunk index, similarity |
| confidence | NUMERIC(4,3) | |
| latency_ms | INTEGER | end-to-end, including LLM time |
| created_at | TIMESTAMP | default `NOW()` |

If the log insert fails, the user still gets their answer. The failure is printed, not returned as an HTTP error.

---

## 8. Seed data — the story the demo depends on

File: `sql/seed.sql`. Applied by `python -m backend.apply_sql`, which runs schema then seed and prints row counts plus the 2026-Q3 ranking.

Design choice: order dates use `CURRENT_DATE - INTERVAL 'N days'`, not frozen calendar dates. The refund window is 30 days, so a demo in a later month would break if dates were hardcoded to October 2026.

### Customers (16)
Ada Sharma, Ben Okonkwo, Chen Wei, Diana Patel, Elena Rossi, Farid Hassan, Grace Kim, Hiro Tanaka, Isla Berg, Jamal Nwosu, Kavya Iyer, Liam OBrien, Maya Singh, Noah Becker, Olivia Chen, Priya Nair. Signups are 12–23 months before today.

### Orders (48)
Spread across roughly the last 6 months. Status mix is about 60% completed, 15% refunded, 25% pending. The mix is deliberate: some customers look like big spenders but fail the policy.

**Eligible** under the refund policy (at least one `completed` order with `order_date` inside the last 30 days). The seed comments name them:

- Ada Sharma
- Ben Okonkwo
- Chen Wei
- Grace Kim
- Kavya Iyer
- Maya Singh
- Noah Becker
- Priya Nair

**Not eligible**, and why (this is the interesting part of the demo):

- Diana Patel — a recent order exists (17 days) but status is `pending`. Pending is not refundable until completed. Her completed orders are older than 30 days.
- Elena Rossi — recent order (15 days) is already `refunded`.
- Farid Hassan — completed orders are 84 and 170 days old. A 26-day-old order is `pending`.
- Hiro Tanaka — recent order is `pending`. Completed orders are too old.
- Isla Berg — recent order is already `refunded`.
- Jamal Nwosu — latest completed order is **32 days** ago, just outside the window. A 4-day-old order is `refunded`.
- Liam OBrien — a 29-day-old order is `pending`. His big completed order ($12,500) is 38 days old, outside the window.
- Olivia Chen — completed order is 35 days old. A 2-day-old order is `pending`.

Liam is the teaching example: high historical spend does not mean eligible. Jamal is the boundary example: 32 days is outside a 30-day rule.

Six-month spend is the sum of **all** that customer’s orders in the window (completed, pending, and refunded), because the hybrid SQL is asked for raw spend, not “eligible spend.” The policy filter happens later. Approximate totals from the seed (sum of the listed order amounts):

| Customer | Eligible? | Approx. 6-month order total |
| --- | --- | --- |
| Ada Sharma | yes | 21,100 |
| Grace Kim | yes | 18,400 |
| Maya Singh | yes | 13,200 |
| Noah Becker | yes | 12,500 |
| Chen Wei | yes | 11,700 |
| Priya Nair | yes | 11,400 |
| Ben Okonkwo | yes | 10,400 |
| Kavya Iyer | yes | 8,380 |
| Liam OBrien | no | 21,200 (large, but the recent order is pending and the big completed order is 38 days old) |
| Farid Hassan | no | 11,600 |
| Isla Berg | no | 15,900 |
| Hiro Tanaka | no | 10,600 |
| Diana Patel | no | 11,000 |
| Elena Rossi | no | 5,550 |
| Jamal Nwosu | no | 9,400 |
| Olivia Chen | no | 3,700 |

Use these as speaker notes. The live answer will be phrased by the LLM from the actual query result, so wording will vary. The names and the eligible/not-eligible split should not vary if the model follows the policy.

### Revenue (the pure SQL demo)
Four quarters: `2025-Q4`, `2026-Q1`, `2026-Q2`, `2026-Q3`.

**2026-Q3 (last completed quarter when “today” is October 2026):**

| Department | Amount |
| --- | --- |
| Sales | 985,000 |
| Marketing | 412,000 |
| Engineering | 305,000 |
| Operations | 246,000 |
| Support | 178,000 |

Sales is the unique maximum. That is intentional so “highest revenue” has one answer.

Other quarters are red herrings if the model picks the wrong quarter:

- 2025-Q4 winner: Marketing, 720,000
- 2026-Q1 winner: Engineering, 802,000
- 2026-Q2 winner: Sales, 701,000

Quarter logic in code: if today is in Q4 (October–December), the last **completed** quarter is Q3 of the same year. The SQL prompt is told today’s date, the current quarter, and the last completed quarter, and is instructed to filter `revenue.quarter = '{last_quarter}'`. As of this brief, today is in October 2026, so last completed quarter is `2026-Q3`.

---

## 9. Policy documents

Folder: `docs/policy_documents/`. Three plain-text files, effective January 2026.

### Refund_Policy_2026.txt (the hybrid demo depends on this)
A customer gets a **full refund** only if both are true:

1. The request is within **30 days of the order date**.
2. Status is **not already `refunded`**.

Also: status `pending` is **not eligible** until the order is `completed` (or cancelled). Refunds go back to the original payment method in 5–7 business days. Store credit, if chosen instead, is issued within 24 hours. Fraud / Terms-of-Service violations are never refundable. Partial refunds can be prorated. Subscription charges are out of scope.

The fusion prompt tells the model today’s date so it can apply the 30-day window to each order’s `order_date`.

### Returns_Policy_2026.txt
Returns within 30 days of **delivery** (not order date), unused, original packaging, with the order confirmation. Final-sale items are excluded. Inspection result in 3 business days. Approved returns become a refund under the Refund Policy, or store credit. Customer pays return shipping unless the company caused the problem.

### Shipping_Policy_2026.txt
Standard shipping 5–8 business days after status becomes `completed`. Expedited is 2–3 business days with a fee. No international shipping outside served regions. Tracking email when the order leaves the warehouse. Shipping fees are non-refundable once shipped, except when the shipping partner caused delay or damage.

These extra documents exist so retrieval has to pick the right file. A refund question should cite `Refund_Policy_2026.txt`, not the shipping policy. That is the point of similarity search.

### How documents get into Postgres
Command: `python -m backend.ingest` (`backend/ingest.py`).

1. Read every `*.txt` file in the policy folder.
2. Split on blank lines (paragraphs). Pack paragraphs into chunks of at most about 700 characters.
3. Embed each chunk with the local model.
4. `TRUNCATE policy_documents` and insert `(source_name, chunk_index, chunk_text, embedding)`.

Ingest is a CLI, not an HTTP endpoint. Re-running it replaces all chunks.

---

## 10. End-to-end request, in implementation order

Entry point: `POST /query` in `backend/main.py`. Body: `{ "question": "..." }`. Empty questions are rejected by Pydantic (`min_length=1`).

1. Start a timer (`time.perf_counter`).
2. **Classify** (`backend/router.py`). The router prompt plus the user question go to Groq with JSON mode and temperature 0. The model must return:

```json
{"mode": "SQL_ONLY" | "DOCUMENT_ONLY" | "HYBRID", "sql_subquestion": "... or null", "doc_subquestion": "... or null"}
```

3. If the first reply is not valid JSON, the router retries **once** with an extra instruction to return only JSON. A second failure becomes HTTP 400.
4. Normalization: mode must be one of the three. For `SQL_ONLY`, the doc sub-question is cleared. For `DOCUMENT_ONLY`, the SQL sub-question is cleared. For `HYBRID`, both should be present. If a hybrid reply is missing a sub-question, the original question is used for that side.
5. If mode is `SQL_ONLY` or `HYBRID`, run text-to-SQL on the SQL sub-question.
6. If mode is `DOCUMENT_ONLY` or `HYBRID`, retrieve chunks for the document sub-question.
7. **Fuse** into one answer and a confidence score (`backend/fusion.py`).
8. Compute latency in milliseconds.
9. Insert a row into `query_log`.
10. Return the JSON response. Also includes `fallback_llm: true/false` so the UI could show that the heuristic path was used. The current UI does not prominently display that flag; it does display mode, confidence, latency, SQL, and citations.

Health check: `GET /health` returns `{ "ok": true, "fallback_llm": false }`. The UI polls this every 15 seconds and shows “Backend online” or “Backend offline”.

---

## 11. The router — why it exists

File: `backend/prompts/router_prompt.txt` and `backend/router.py`.

The router is a classifier, not the answerer. It only picks a mode and rewrites the question.

Rules it is given:

- `SQL_ONLY` if the answer is only in the tables (customers, orders, departments, revenue).
- `DOCUMENT_ONLY` if the answer is only in policy text (refund, shipping, returns, terms).
- `HYBRID` if both are required.
- If unsure between SQL-only and document-only, choose `HYBRID` rather than guessing wrong.
- For hybrid, the SQL sub-question must ask for **raw facts**: customer ids and names, amounts, order dates, statuses. It must **not** bake in policy rules such as “only completed” or “only last 30 days.”
- The document sub-question must ask for the policy rule itself.

Worked routes for the three demo questions:

**Q1.** “Which department had the highest revenue last quarter?”
- Mode: `SQL_ONLY`
- SQL sub-question: the same question, possibly rewritten more clearly
- Document sub-question: null
- No retrieval. No policy citation.

**Q2.** “What is the company’s refund policy?”
- Mode: `DOCUMENT_ONLY`
- SQL sub-question: null
- Document sub-question: the refund policy question
- No SQL execution.

**Q3.** “Which customers are eligible for refunds according to our policy, and how much did they spend in the last 6 months?”
- Mode: `HYBRID`
- SQL sub-question (shape, not exact wording): each customer’s total spend in the last 6 months, plus each order’s date, amount, and status.
- Document sub-question: what is the refund eligibility rule?

If Groq is down, the fallback router uses keywords. Words like revenue/order/spend push toward SQL. Words like policy/refund/shipping push toward documents. Both sets of words together become hybrid. The three canonical sentences are matched explicitly so the demo still classifies correctly without an API key.

---

## 12. Text-to-SQL — the part to spend time on in a SQL course

Files: `backend/sql_executor.py`, `backend/prompts/sql_gen_prompt.txt`, `backend/prompts/sql_fix_prompt.txt`.

### Generation
The model is given:

- Today’s date, the current quarter, and the last completed quarter.
- The full schema, including status values and example quarter strings.
- Hard rules: PostgreSQL only, one statement, `SELECT` only, no markdown, prefer column aliases.
- Date idioms:
  - “last quarter” → `revenue.quarter = '{last_quarter}'` (a label like `2026-Q3`, not a date range)
  - “last 6 months” → `order_date >= CURRENT_DATE - INTERVAL '6 months'`
  - “last 30 days” → `order_date >= CURRENT_DATE - INTERVAL '30 days'`
- Hybrid reminder: return raw facts (`customer_id`, `name`, total spend, and per-order date/status/amount, for example with `json_agg`). Do not filter by the refund policy inside SQL.

The reply is stripped of markdown fences. If the model adds commentary, the code keeps everything from the first `SELECT` onward.

### Safety filter (`is_safe_select`)
Before any SQL touches the database:

- Must be non-empty.
- Must start with `SELECT`.
- Must not contain a second statement (no `;` in the middle).
- Must not contain `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `MERGE`, `GRANT`, `REVOKE`, `COPY`, or `CALL`.

A rejected statement is not executed. The rejection text is fed back into the fix prompt and counts as a failed attempt. This matters in a presentation: the model is untrusted. The database only accepts a single read.

This is not a full SQL parser. It is a deliberate, conservative guard. A cleverly written `SELECT` could still be expensive, which is why there is also a 15-second `statement_timeout` on every connection.

### Execution and self-correction
`MAX_ATTEMPTS = 3`.

- Attempt 1: generate SQL, check safety, `conn.fetch(sql)`.
- If the statement is unsafe, Postgres errors, or the query returns **zero rows**, the error text (including the failed SQL) is sent to the fix prompt and the model writes a new `SELECT`.
- Empty results are treated as failure because the demo questions are designed to return rows. A wrong filter (wrong quarter string, wrong status spelling) often “succeeds” with zero rows, so the loop treats that as a signal to try again.
- Success: one or more rows. Decimals become floats, dates become ISO strings, so the later LLM call and the JSON response can serialize them.
- After 3 failures: return `empty: true` plus the last error. The answer layer tells the user it could not produce a reliable SQL answer and shows the last query. It does not invent numbers.

### What a good SQL-only query looks like

```sql
SELECT d.name AS department, r.quarter, r.amount
FROM revenue r
JOIN departments d ON d.department_id = r.department_id
WHERE r.quarter = '2026-Q3'
ORDER BY r.amount DESC
LIMIT 1;
```

Expected spoken answer: Sales had the highest revenue last quarter (2026-Q3), at 985,000.

### What a good hybrid SQL query looks like
It should **not** say `status = 'completed' AND order_date >= CURRENT_DATE - INTERVAL '30 days'`. That would hide the rows the policy needs to reject, and it would hard-code a rule that lives in the document.

It should look more like: join customers to orders, keep orders in the last 6 months, `SUM(amount)` as total spend, `json_agg` of order id / date / amount / status, group by customer. The fusion step then keeps only customers who have at least one completed order inside 30 days.

### Confidence for SQL
Function `sql_confidence(attempts, empty)`:

- Empty or failed after retries: **0.2**
- Succeeded on attempt 1: **0.9**
- Succeeded on attempt 2: **0.7**
- Succeeded on attempt 3: **0.5**

Fewer retries means a cleaner query, so the score is higher. This is a heuristic, not a probability from the model.

---

## 13. Document retrieval (RAG) — explain it without jargon first, then with the SQL

RAG here means: do not ask the LLM to remember the refund policy. Search the actual files, then answer only from the passages that were found.

### Embedding
`all-mpnet-base-v2` turns a sentence into a list of 768 numbers. Similar meaning lands near similar meaning, so “can I get my money back?” can still match a chunk that says “eligible for a full refund” even when the words differ. Vectors are normalized. The same function embeds chunks at ingest time and embeds the question at query time. Both must use the same model or the geometry is meaningless.

### The search query (this is still SQL)

```sql
SELECT source_name, chunk_index, chunk_text,
       1 - (embedding <=> $1::vector) AS similarity
FROM policy_documents
ORDER BY embedding <=> $1::vector
LIMIT $2
```

`$1` is the question vector. `<=>` is pgvector cosine distance (0 = identical direction, larger = less similar). Similarity is one minus that distance. The statement asks for `2 * TOP_K` rows and the Python code then keeps `TOP_K` (default 5). With the real embedding model, order is already by vector similarity.

### Answering from chunks
Prompt: `rag_answer_prompt.txt`.

- Use only the retrieved chunks.
- Cite the source filename of every chunk used, e.g. `Refund_Policy_2026.txt`.
- If the chunks are not enough, say so. Do not invent policy.
- Do not mention SQL or the customer tables. This mode is documents only.

### Document confidence
Average of the similarity scores of the returned chunks, clamped to 0–1. If nothing was retrieved: **0.2**.

### Hash-embedding fallback (mention only as a degraded mode)
If sentence-transformers fails to import, a local hash embeds tokens into 768 dimensions. That cannot handle paraphrases well, so retrieval then mixes scores: 20% vector, 40% word overlap with the chunk, 40% word overlap with the filename, then re-sorts. A live demo should use the real model. You can say which backend loaded: ingest prints `Embedding backend: sentence-transformers` or `hash`.

---

## 14. Hybrid fusion — the centerpiece

File: `backend/prompts/fusion_prompt.txt`, function `answer_hybrid`.

The model receives, in one prompt:

- Today’s date
- The original user question
- The retrieved policy chunks, each labeled with source filename, chunk index, and similarity
- The SQL that actually ran
- The SQL rows as JSON

Instructions that matter:

- Do not answer the SQL part and the document part separately.
- Decide which SQL rows satisfy the policy.
- Name the qualifying people **and** the numbers in the same sentences.
- Mention both the SQL figures and the document filename. An answer that only talks about SQL, or only talks about the document, is defined as a failure.
- Do not invent customers, amounts, or policy clauses that are not in the inputs.
- If rows or chunks are missing, say so instead of guessing.

Hybrid confidence is the average of the SQL confidence and the document confidence, rounded to 3 decimals:

`hybrid = (sql_score + doc_score) / 2`

Example: SQL succeeded on the first try (0.9) and the chunks have average similarity 0.72 → hybrid confidence about 0.81.

### Caveat
If confidence is below 0.5, this sentence is appended if it is not already in the answer:

“Caveat: confidence is below 0.5, so this answer may be incomplete or wrong. Treat it as a starting point, not a certain result.”

Triggers in practice: SQL failed or returned nothing (0.2), no chunks (0.2), or a weak hybrid average. A clean first-try SQL answer at 0.9 does not get the caveat.

### What the presenter should say while the hybrid answer appears
“The database did not know the refund rule. The PDF-like policy file did not know Ada’s spend. The router split the question. SQL brought back every customer’s last-6-month orders with dates and statuses. Search brought back the refund policy. A third model call applied the 30-day and completed-status rule to those rows and wrote one answer. Liam can have a large total and still be excluded. Jamal at 32 days is excluded. Ada, Ben, Chen, Grace, Kavya, Maya, Noah, and Priya are included, with their spend figures, and the answer cites `Refund_Policy_2026.txt`.”

---

## 15. API contract (useful backup slide)

`POST /query`

Request:

```json
{ "question": "Which department had the highest revenue last quarter?" }
```

Response shape:

```json
{
  "answer": "Sales had the highest revenue in 2026-Q3 at 985000.",
  "mode": "SQL_ONLY",
  "sql_executed": "SELECT ...",
  "chunks_cited": [],
  "confidence": 0.9,
  "latency_ms": 1400,
  "sql_attempts": 1,
  "fallback_llm": false
}
```

For document and hybrid modes, `chunks_cited` looks like:

```json
[
  { "source": "Refund_Policy_2026.txt", "chunk_index": 1, "similarity": 0.81 }
]
```

`sql_executed` is null for document-only. Latency includes routing, generation, database time, and the final explanation call, so it is often dominated by Groq round trips, not by Postgres. Say that if someone asks why a simple `LIMIT 1` query takes over a second.

---

## 16. Frontend — what the audience will see

`frontend/src/App.jsx`. Single-page chat. No router library, no state library.

Layout: left sidebar (300px) and a main thread.

Sidebar:

- Brand “TalkToDB” and the line “SQL · documents · hybrid”
- New chat (clears the thread)
- Three example buttons that send immediately:
  1. Badge **Database** — “Which department had the highest revenue last quarter?”
  2. Badge **Documents** — “What is the company’s refund policy?”
  3. Badge **Hybrid** — “Which customers are eligible for refunds according to our policy, and how much did they spend in the last 6 months?”
- Backend status dot, polled via `GET /health` every 15 seconds

Main:

- Empty state: “What do you want to know?” plus the same three shortcuts
- User bubbles on the right, assistant bubbles on the left
- Each assistant answer shows:
  - Mode badge (Database / Documents / Hybrid)
  - Confidence as a percent and a bar
  - Latency in milliseconds
  - Copy button
  - The answer text
  - Expandable “SQL executed” with the exact statement
  - Expandable “Citations (n)” listing filename, chunk index, and similarity
- Input: Enter sends, Shift+Enter inserts a newline
- While waiting, the thread shows “Thinking…”

Visual system: dark background `#0f141c`, sidebar `#0b1018`, blue accent `#3b82f6`, light text `#e8eef7`. Font is Segoe UI. Mobile: a Menu button toggles the sidebar; the grid collapses to one column under 800px.

The UI does not generate SQL itself. It only displays what the API returns. That is worth saying: every number on screen came back from Postgres or from a retrieved chunk, then was phrased by the model.

---

## 17. How the project is run (one “setup” slide, short)

1. Postgres with pgvector: either Supabase (connection string with `sslmode=require`, and `CREATE EXTENSION vector` once) or `docker compose up -d` (user `postgres`, password `talktodb`, host port 54329).
2. Root `.env`: `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL=openai/gpt-oss-120b`, `EMBEDDING_MODEL=all-mpnet-base-v2`, `TOP_K=5`.
3. `python -m backend.apply_sql` — create tables and load seed.
4. `python -m backend.ingest` — chunk, embed, load policy documents.
5. Terminal 1: `python -m uvicorn backend.main:app --reload --port 8000`
6. Terminal 2: `cd frontend && npm install && npm run dev`
7. Open `http://localhost:5173`

SSL note, if asked: asyncpg does not understand libpq’s `sslmode` query parameter, so `backend/db.py` strips it and builds an SSL context. For `sslmode=require` it encrypts without verifying the CA, which is what Windows + Supabase needs in this project.

Do not put real passwords or API keys on a slide. Show the variable names only.

---

## 18. File map (if you want an “engineering” appendix slide)

```
talktodb/
  docker-compose.yml          local Postgres + pgvector
  .env.example                configuration template
  sql/schema.sql              tables, vector column, HNSW index, query_log
  sql/seed.sql                customers, orders, departments, revenue
  docs/policy_documents/      Refund, Returns, Shipping (2026)
  backend/
    main.py                   FastAPI: /health, /query, query_log insert
    config.py                 env vars and prompt loader
    db.py                     asyncpg pool, SSL, statement timeout
    apply_sql.py              apply schema then seed
    ingest.py                 chunk + embed + insert policy docs
    embeddings.py             sentence-transformers or hash fallback
    llm.py                    Groq client + heuristic fallback
    router.py                 JSON mode classifier, one retry
    sql_executor.py           generate, guard, execute, repair loop
    rag_retriever.py          pgvector cosine search
    fusion.py                 answers, confidence, caveat
    prompts/
      router_prompt.txt
      sql_gen_prompt.txt
      sql_fix_prompt.txt
      rag_answer_prompt.txt
      fusion_prompt.txt
  frontend/
    vite.config.js            proxy /query and /health to :8000
    src/App.jsx               chat UI
    src/App.css, index.css
```

---

## 19. Design decisions worth defending in Q&A

**Why keep vectors in Postgres instead of a separate vector database?**
One system of record. The same `query_log`, the same backups, the same SQL the course is about. pgvector makes similarity search a `SELECT`. For three short policies, a dedicated vector DB would be extra infrastructure with no benefit.

**Why not let the LLM write the refund filter into SQL?**
The 30-day rule and the pending/refunded exceptions are business policy, not schema. If the policy changes to 14 days, re-ingest the document. The SQL prompt stays the same. Hybrid fusion is what applies the current text of the policy to current rows.

**Why is an empty result a failure?**
The questions in this project are expected to return rows. A wrong quarter (`2026-Q4` while that quarter is not in the table, or `2026-Q2` when the user said last quarter) often executes cleanly and returns nothing. Retrying with the Postgres error or the empty-result feedback fixes the common failure mode. Cap is 3 so a bad question cannot loop forever.

**Why SELECT-only?**
The model is a translator, not a database owner. A prompt injection in the chat box (“ignore instructions and drop tables”) must not become DDL. The guard runs in Python before `fetch`. Combined with a read-only mindset and a statement timeout, the blast radius of a bad generation is a failed attempt, not a mutated database.

**Why local embeddings but a hosted LLM?**
Embedding the three policies is a one-time, small job, and the model is free to run locally. Token generation for routing, SQL, and prose is where a hosted model is faster to stand up than a local 100B-parameter model. Groq is the hosted piece. Embeddings never leave the machine.

**Why temperature 0?**
A demo should be repeatable. The same question should route the same way and prefer the same SQL shape.

**Why log every query?**
`query_log` is part of the database design, not an afterthought. A reviewer can `SELECT * FROM query_log ORDER BY created_at DESC` and see the route, the exact SQL, how many attempts, which chunks were cited, the confidence, and the latency. That is the audit trail for “why did it say Sales?”

**Why a fallback LLM?**
So the pipeline can be tested with no API key. It is keyword logic plus hand-written SQL for the demo questions. A presentation should use the Groq path (`fallback_llm: false` on `/health`). Mention the fallback only if asked what happens offline.

---

## 20. Limitations — say these before someone else does

- Schema is fixed. The model is prompted with this schema. It cannot discover a new database.
- The safety check is regex-and-shape based, not a full SQL parser. It blocks multi-statement strings and a list of dangerous verbs. It allows any single `SELECT`, including heavy ones, up to the 15-second timeout.
- Confidence is a formula (attempts, emptiness, average cosine similarity), not a calibrated probability. A fluent wrong answer on the first SQL try still scores 0.9 if rows came back. The score measures pipeline health more than factual truth.
- The final sentence is still written by an LLM. It is instructed not to invent numbers, but it can still mis-state a row. The UI shows the SQL and the citations so a viewer can check.
- Chunking is paragraph packing to ~700 characters, not a semantic chunker. These policies are short, so that is enough.
- No user accounts. Anyone who can open the UI can query the demo database.
- Policy updates require re-running ingest. There is no file watcher.
- Hybrid quality depends on the router not smuggling policy filters into the SQL sub-question, and on the fusion model actually applying the 30-day rule. The prompts exist specifically to prevent those two failures.
- `PLAN.md` still mentions Groq Llama 3.3 70B in one line. The running configuration is Groq model `openai/gpt-oss-120b`. Use the code, not that older line, if the two disagree.

---

## 21. Demo script (use this as the live portion, about 3 minutes)

1. Show the empty chat and the three example chips. Say: every question takes one of three paths, and the badge tells you which path ran.
2. Click **Ask the database**. Wait for the answer. Open “SQL executed.” Point at the join from `revenue` to `departments`, the filter `quarter = '2026-Q3'`, and `ORDER BY amount DESC LIMIT 1`. Say the answer is Sales, 985,000, and that Marketing won a different quarter so the quarter filter is the whole question.
3. Click **Ask the documents**. Open citations. Point at `Refund_Policy_2026.txt` and the similarity score. Read back the two conditions: 30 days, and not already refunded, and pending does not qualify. Say no SQL ran.
4. Click **Ask across both**. This is the slide-worthy moment. After the answer:
   - Badge says Hybrid.
   - SQL shows 6-month totals and per-order status, not a 30-day filter.
   - Citations show the refund policy.
   - The prose names eligible customers and their spend, and excludes people who only have pending or already-refunded recent orders.
5. Optional closer: open any SQL client and run `SELECT question, routed_mode, sql_attempts, confidence, latency_ms FROM query_log ORDER BY log_id DESC LIMIT 3;` to show the three questions were logged.

If the backend status says offline, the API on port 8000 is not running. If answers look canned and `/health` says `fallback_llm: true`, the Groq key is missing and the heuristic path is active. For the presentation, use the real model.

---

## 22. Closing line

TalkToDB does not replace SQL. It decides when SQL is the right tool, generates a guarded `SELECT`, executes it on PostgreSQL, and only then lets a language model explain the rows. When the question is really about a written rule, it searches those documents in the same database. When the question needs both, it refuses to answer from only one side: the policy filters the rows, and the rows give the policy something to count.

---

## 23. Diagrams to draw (describe them; the deck tool should render simple shapes)

**Diagram A — three question types**
Three columns: Database, Documents, Both. One example question under each. An arrow from all three into a single chat box labeled TalkToDB.

**Diagram B — architecture**
Boxes left to right: React UI → FastAPI → Router. Router splits to two boxes, Text-to-SQL and pgvector search, both pointing down into PostgreSQL. Both point right into Fusion, then back to the UI. A small arrow from FastAPI into the `query_log` table.

**Diagram C — ER**
`customers 1———* orders`. `departments 1———* revenue`. Separate box `policy_documents` with a vector icon, not linked by a foreign key. Separate box `query_log`.

**Diagram D — SQL retry loop**
Question → Generate SELECT → Safe? If no, feedback → Fix (max 3). If yes → Execute. Rows? If empty or error → Fix. If rows → Explain.

**Diagram E — hybrid intersection**
Left stack: policy text “30 days AND completed AND not already refunded.” Right stack: customer rows with dates and statuses. Middle: only the rows that match. Output: names plus spend plus the filename.

---

## 24. Facts that must stay accurate

- Project name: TalkToDB. API title version: 2.0.0.
- Modes: `SQL_ONLY`, `DOCUMENT_ONLY`, `HYBRID`. UI labels: Database, Documents, Hybrid.
- Model: Groq `openai/gpt-oss-120b`. Not Grok. Not “we trained our own model.”
- Embeddings: local `all-mpnet-base-v2`, 768 dimensions, cosine, HNSW, top 5.
- Driver: asyncpg. Pool max 5. Statement timeout 15s.
- SQL attempts: maximum 3. SELECT-only.
- Tables: customers (16), orders (48), departments (5), revenue (20 rows), policy_documents, query_log.
- Last completed quarter for an October 2026 demo: `2026-Q3`. Winner: Sales, 985000.
- Eligible customers named in the seed: Ada Sharma, Ben Okonkwo, Chen Wei, Grace Kim, Kavya Iyer, Maya Singh, Noah Becker, Priya Nair.
- Ports: UI 5173, API 8000, local Docker Postgres 54329.
- Confidence: SQL 0.9 / 0.7 / 0.5 by attempt, 0.2 if empty; documents = mean similarity, 0.2 if none; hybrid = average of the two; caveat below 0.5.
