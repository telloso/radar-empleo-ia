"""SQLAlchemy ORM mapping of the tables the API reads.

The tables are still created by the SQL files in db/init/: these classes only
describe them to Python (no create_all, no migrations). Only the columns the
API uses are mapped.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    company: Mapped[str]
    location: Mapped[str]
    url: Mapped[str]
    # "| None" makes the column nullable, like published_at in the SQL table.
    published_at: Mapped[datetime | None]
    salary: Mapped[str | None]
    description: Mapped[str]


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    prompt_version: Mapped[str]
    model: Mapped[str]
    score: Mapped[int]
    fit: Mapped[str]
    # Postgres TEXT[]: SQLAlchemy needs to be told, it cannot guess it from list[str].
    matched_skills: Mapped[list[str]] = mapped_column(ARRAY(Text))
    missing_skills: Mapped[list[str]] = mapped_column(ARRAY(Text))
    salary_ok: Mapped[bool | None]
    reasons: Mapped[str]
    scored_at: Mapped[datetime]
