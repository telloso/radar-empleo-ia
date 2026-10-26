"""Job embedder: splits every job not embedded yet into chunks and stores their vectors.

The embedding model runs locally (fastembed + ONNX): no API key and no cost per call.
"""

import html
import logging
import os
import re
import sys

import psycopg
from fastembed import TextEmbedding
from psycopg.rows import dict_row

import db

logger = logging.getLogger("embedder")

# Multilingual, because most offers are in Spanish. It reads at most 128 tokens per
# text (about 80 words) and cuts the rest, which is why long offers are chunked.
MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_WORDS = 60
# Consecutive chunks share some words, so a sentence cut in two still appears whole once.
OVERLAP_WORDS = 15

TAG = re.compile(r"<[^>]+>")

# Jobs with no chunks for the current model (same LEFT JOIN ... IS NULL as the scorer).
PENDING_JOBS = """
SELECT j.id, j.title, j.company, j.location, j.description
FROM jobs j
LEFT JOIN job_chunks c ON c.job_id = j.id AND c.model = %(model)s
WHERE c.job_id IS NULL
ORDER BY j.id
"""

INSERT_CHUNK = """
INSERT INTO job_chunks (job_id, chunk_index, model, content, embedding)
VALUES (%(job_id)s, %(chunk_index)s, %(model)s, %(content)s, %(embedding)s::vector)
ON CONFLICT (job_id, model, chunk_index) DO NOTHING
"""


def html_to_text(raw: str) -> str:
    """Remotive sends the description as HTML; keep only the words."""
    return " ".join(html.unescape(TAG.sub(" ", raw)).split())


def chunk_job(job: dict) -> list[str]:
    """Split a job into overlapping chunks of CHUNK_WORDS words.

    Every chunk starts with the title and company, so a chunk taken out of
    context ("experience with Terraform...") still says which job it belongs to.
    """
    header = f"{job['title']} | {job['company']} | {job['location'] or 'no location'}"
    words = html_to_text(job["description"]).split()
    if not words:
        return [header]

    step = CHUNK_WORDS - OVERLAP_WORDS
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(f"{header}\n{' '.join(words[start:start + CHUNK_WORDS])}")
        if start + CHUNK_WORDS >= len(words):
            break
    return chunks


def load_model() -> TextEmbedding:
    """Load the embedding model (downloaded once, then read from the local cache)."""
    return TextEmbedding(MODEL)


def to_pgvector(vector) -> str:
    """Write a vector the way pgvector reads it as text: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        conn = db.connect()
    except psycopg.OperationalError as exc:
        logger.error("cannot connect to the database: %s", exc)
        return 1

    with conn:
        with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
            cur.execute(PENDING_JOBS, {"model": MODEL})
            jobs = cur.fetchall()
        logger.info("%d jobs to embed with %s", len(jobs), MODEL)
        if not jobs:
            return 0

        model = load_model()
        total = 0
        for job in jobs:
            chunks = chunk_job(job)
            vectors = model.embed(chunks)
            # One transaction per job: a job is either fully embedded or not at all,
            # so the LEFT JOIN above never sees a half-done job as finished.
            with conn.transaction(), conn.cursor() as cur:
                for index, (content, vector) in enumerate(zip(chunks, vectors)):
                    cur.execute(INSERT_CHUNK, {
                        "job_id": job["id"],
                        "chunk_index": index,
                        "model": MODEL,
                        "content": content,
                        "embedding": to_pgvector(vector),
                    })
            total += len(chunks)
            logger.info("job %d: %d chunks (%s)", job["id"], len(chunks), job["title"])

    logger.info("%d jobs embedded, %d chunks", len(jobs), total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
