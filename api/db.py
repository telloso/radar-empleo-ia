"""Read-only access to the Radar database for the API."""

import os

import psycopg
from psycopg.rows import dict_row

from schemas import JobDetail, JobSummary, Score

# A job can have several scores (one per prompt version); like the Telegram digest,
# the API always uses the newest one, so both show the same numbers.
LATEST_SCORES = """
    SELECT DISTINCT ON (job_id) *
    FROM scores
    ORDER BY job_id, scored_at DESC
"""

# %(fit)s IS NULL makes the filter optional: no fit given means every fit.
TOP_JOBS = f"""
WITH latest AS ({LATEST_SCORES})
SELECT j.id, j.title, j.company, j.location, j.url, j.published_at, l.score, l.fit
FROM jobs AS j
JOIN latest AS l ON l.job_id = j.id
WHERE %(fit)s::text IS NULL OR l.fit = %(fit)s
ORDER BY l.score DESC, j.published_at DESC NULLS LAST
LIMIT %(limit)s
"""

# LEFT JOIN: a job that has not been scored yet still comes back, with NULL score columns.
JOB = f"""
WITH latest AS ({LATEST_SCORES})
SELECT j.id, j.title, j.company, j.location, j.url, j.published_at, j.salary,
       j.description, l.score, l.fit, l.salary_ok, l.matched_skills,
       l.missing_skills, l.reasons, l.model, l.scored_at
FROM jobs AS j
LEFT JOIN latest AS l ON l.job_id = j.id
WHERE j.id = %(id)s
"""

SCORE_FIELDS = set(Score.model_fields)


def connect() -> psycopg.Connection:
    """Open a connection as the read-only api_reader role (db/init/07-create-api-reader.sh)."""
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.getenv("API_DB_USER", "api_reader"),
        password=os.environ["API_READER_PASSWORD"],
        connect_timeout=5,
        row_factory=dict_row,
    )


class JobRepository:
    """Every query the API runs, behind two methods. The endpoints only see this
    class, so the tests can swap it for a fake one without a database."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def top_jobs(self, limit: int, fit: str | None = None) -> list[JobSummary]:
        rows = self.conn.execute(TOP_JOBS, {"limit": limit, "fit": fit}).fetchall()
        return [JobSummary(**row) for row in rows]

    def get_job(self, job_id: int) -> JobDetail | None:
        row = self.conn.execute(JOB, {"id": job_id}).fetchone()
        if row is None:
            return None
        score = {key: row.pop(key) for key in SCORE_FIELDS}
        has_score = score["score"] is not None
        return JobDetail(**row, score=Score(**score) if has_score else None)
