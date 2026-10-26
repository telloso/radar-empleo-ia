-- Jobs split into short chunks, each with its embedding, for similarity search (RAG).
-- Needs the pgvector extension (image pgvector/pgvector:pg17-trixie).
-- Runs only on the first start; on an existing volume apply it by hand with psql.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS job_chunks (
    id          BIGSERIAL   PRIMARY KEY,
    job_id      BIGINT      NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    -- Position of the chunk inside the job: 0 is the start of the offer.
    chunk_index SMALLINT    NOT NULL,
    -- Vectors from different models are not comparable: keep track of which one made it.
    model       TEXT        NOT NULL,
    -- The exact text that was embedded; it is what gets shown to Claude and cited.
    content     TEXT        NOT NULL,
    -- 384 = output size of the embedding model (paraphrase-multilingual-MiniLM-L12-v2).
    embedding   VECTOR(384) NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, model, chunk_index)
);
