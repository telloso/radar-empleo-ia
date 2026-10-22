"""PostgreSQL storage for collected jobs (table created by db/init/02-create-jobs.sql)."""

import os
from dataclasses import asdict

import psycopg

from models import Job

# New offers are inserted; offers we already have get their data refreshed and
# last_seen_at moved to now. EXCLUDED is the row we tried to insert.
UPSERT_JOB = """
INSERT INTO jobs (source, external_id, title, company, location, url,
                  published_at, salary, description)
VALUES (%(source)s, %(external_id)s, %(title)s, %(company)s, %(location)s, %(url)s,
        %(published_at)s, %(salary)s, %(description)s)
ON CONFLICT (source, external_id) DO UPDATE SET
    title        = EXCLUDED.title,
    company      = EXCLUDED.company,
    location     = EXCLUDED.location,
    url          = EXCLUDED.url,
    published_at = EXCLUDED.published_at,
    salary       = EXCLUDED.salary,
    description  = EXCLUDED.description,
    last_seen_at = now()
RETURNING first_seen_at = last_seen_at AS is_new
"""


def connect() -> psycopg.Connection:
    """Open a connection using the same POSTGRES_* variables as the db service."""
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    )


def save_jobs(conn: psycopg.Connection, jobs: list[Job]) -> int:
    """Insert or refresh `jobs` in one transaction and return how many were new."""
    new = 0
    with conn.transaction(), conn.cursor() as cur:
        for job in jobs:
            row = asdict(job)
            # Jooble sometimes sends no date; an empty string is not a valid timestamp.
            row["published_at"] = row["published_at"] or None
            cur.execute(UPSERT_JOB, row)
            if cur.fetchone()[0]:
                new += 1
    return new
