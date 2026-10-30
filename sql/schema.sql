-- TalkToDB schema: PostgreSQL + pgvector (Supabase-compatible)
-- Idempotent: safe to re-run during development.

DROP TABLE IF EXISTS query_log CASCADE;
DROP TABLE IF EXISTS policy_documents CASCADE;
DROP TABLE IF EXISTS revenue CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE customers (
    customer_id     SERIAL PRIMARY KEY,
    name            VARCHAR(200),
    email           VARCHAR(200),
    signup_date     DATE
);

CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(customer_id),
    order_date      DATE,
    amount          NUMERIC(10,2),
    status          VARCHAR(50)
);

CREATE TABLE departments (
    department_id   SERIAL PRIMARY KEY,
    name            VARCHAR(100)
);

CREATE TABLE revenue (
    revenue_id      SERIAL PRIMARY KEY,
    department_id   INTEGER REFERENCES departments(department_id),
    quarter         VARCHAR(10),
    amount          NUMERIC(12,2)
);

CREATE TABLE policy_documents (
    doc_id          SERIAL PRIMARY KEY,
    source_name     VARCHAR(200),
    chunk_index     INTEGER,
    chunk_text      TEXT,
    embedding       VECTOR(768)
);

CREATE INDEX policy_docs_hnsw_idx
    ON policy_documents
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE query_log (
    log_id          SERIAL PRIMARY KEY,
    question        TEXT,
    routed_mode     VARCHAR(20),
    sql_generated   TEXT,
    sql_attempts    INTEGER,
    chunks_cited    JSONB,
    confidence      NUMERIC(4,3),
    latency_ms      INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);
