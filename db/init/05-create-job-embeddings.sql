-- One embedding per job: its meaning as a vector, for similarity search (RAG).
-- Needs the pgvector extension (image pgvector/pgvector:pg17).
-- Runs only on the first start; on an existing volume apply it by hand with psql.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS job_embeddings (
    job_id      BIGINT      PRIMARY KEY REFERENCES jobs (id) ON DELETE CASCADE,
    -- Vectors from different models are not comparable: keep track of which one made it.
    model       TEXT        NOT NULL,
    -- 384 = output size of the embedding model (paraphrase-multilingual-MiniLM-L12-v2).
    embedding   VECTOR(384) NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
