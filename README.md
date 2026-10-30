# TalkToDB

A hybrid RAG + text-to-SQL assistant. Natural-language questions are routed to PostgreSQL, policy documents (pgvector), or both, then fused into one cited answer.

## Stack

- PostgreSQL + pgvector (Supabase free tier, or local Docker)
- Groq `openai/gpt-oss-120b` (this is Groq, not xAI Grok)
- Local embeddings: `sentence-transformers` / `all-mpnet-base-v2` (768-dim)
- FastAPI backend, React + Vite frontend

---

## 1. Groq API key (LLM)

No credit card.

1. Open [https://console.groq.com](https://console.groq.com) and sign up (Google/GitHub/email).
2. In the left sidebar go to **API Keys**.
3. Click **Create API Key**, give it a name (e.g. `talktodb`), and **copy it immediately** — Groq shows it only once.
4. It should look like `gsk_...`.

Keep this value for `.env` as `GROQ_API_KEY`.

---

## 2. Supabase (Postgres + pgvector)

No credit card. This is the database, not a REST “API key” — TalkToDB uses the **Postgres connection string**.

1. Open [https://supabase.com](https://supabase.com) and sign up (GitHub or email).
2. Click **New Project**.
   - Name: `talktodb`
   - Database password: create a strong one and **save it**
   - Region: closest to you
   - Create the project and wait ~2 minutes.
3. In the project: **Project Settings → Database**.
4. Copy the **Connection string** (URI). Prefer **Session pooler** (port **5432**).
5. Replace `[YOUR-PASSWORD]` in that URI with the database password from step 2.
6. Append `?sslmode=require` if it is not already there. Example shape:

```
postgresql://postgres.xxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require
```

7. Open **SQL Editor** in the Supabase dashboard and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

You do **not** need the Supabase `anon` / `service_role` API keys for this project.

---

## 3. Put both values in `.env`

In the project root (`talktodb/.env`):

```
DATABASE_URL=postgresql://postgres.xxxx:YOUR_PASSWORD@....pooler.supabase.com:5432/postgres?sslmode=require
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=all-mpnet-base-v2
TOP_K=5
```

Then apply schema, seed, and documents, and start the apps:

```powershell
python -m backend.apply_sql
python -m backend.ingest

# terminal 1
python -m uvicorn backend.main:app --reload --port 8000

# terminal 2
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Local database (skip Supabase for now)

```powershell
docker compose up -d
```

Use this in `.env` instead:

```
DATABASE_URL=postgresql://postgres:talktodb@127.0.0.1:54329/postgres
```

You still need a Groq key for real LLM answers. Without it the backend uses a fallback that only handles the demo questions well.
