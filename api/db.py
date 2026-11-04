"""Read-only access to the Radar database for the API, through SQLAlchemy."""

import os
from functools import cache

from sqlalchemy import URL, Engine, create_engine, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, aliased

import models
from schemas import JobDetail, JobSummary, Score

# What main.py catches to answer 503. Named here so main.py does not depend on
# which database library raises it.
DatabaseUnavailable = OperationalError


@cache
def get_engine() -> Engine:
    """The engine holds a pool of open connections that requests borrow and give
    back. Built on first use (not on import), so the tests need no settings."""
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("API_DB_USER", "api_reader"),
        password=os.environ["API_READER_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    # pool_pre_ping: test a pooled connection before using it, in case Postgres restarted.
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def connect() -> Session:
    """A session for one request; use it as `with connect() as session:`."""
    return Session(get_engine())


def latest_scores():
    """Each job's newest score, like the Telegram digest:
    SELECT DISTINCT ON (job_id) * FROM scores ORDER BY job_id, scored_at DESC"""
    newest_first = (
        select(models.Score)
        .distinct(models.Score.job_id)
        .order_by(models.Score.job_id, models.Score.scored_at.desc())
        .subquery()
    )
    # Lets the subquery be used as if it were the Score class itself.
    return aliased(models.Score, newest_first)


def columns(obj: models.Base) -> dict:
    """The mapped columns of a row as a dict (Pydantic ignores the ones it does not use)."""
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


class JobRepository:
    """Every query the API runs, behind two methods. The endpoints only see this
    class, so the tests can swap it for a fake one without a database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def top_jobs(self, limit: int, fit: str | None = None) -> list[JobSummary]:
        score = latest_scores()
        query = (
            select(models.Job, score)
            .join(score, score.job_id == models.Job.id)
            .order_by(score.score.desc(), models.Job.published_at.desc().nulls_last())
            .limit(limit)
        )
        # An optional filter is just an if: the query is built step by step in Python.
        if fit is not None:
            query = query.where(score.fit == fit)
        return [
            JobSummary(**columns(job), score=s.score, fit=s.fit)
            for job, s in self.session.execute(query)
        ]

    def get_job(self, job_id: int) -> JobDetail | None:
        score = latest_scores()
        # Outer join = LEFT JOIN: a job without a score comes back with s = None.
        query = (
            select(models.Job, score)
            .outerjoin(score, score.job_id == models.Job.id)
            .where(models.Job.id == job_id)
        )
        row = self.session.execute(query).first()
        if row is None:
            return None
        job, s = row
        return JobDetail(**columns(job), score=Score(**columns(s)) if s else None)
