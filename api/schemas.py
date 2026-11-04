"""Shapes of the JSON the API returns. FastAPI validates every response against
them and shows them in the interactive docs at /docs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Same three values as the CHECK constraint on scores.fit.
Fit = Literal["high", "medium", "low"]


class JobSummary(BaseModel):
    """One row of a ranking: enough to decide whether to open the offer."""

    id: int
    title: str
    company: str
    location: str
    url: str
    published_at: datetime | None
    score: int
    fit: Fit


class Score(BaseModel):
    """Claude's latest verdict on a job (see collector/scorer.py)."""

    score: int
    fit: Fit
    salary_ok: bool | None
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: str
    model: str
    scored_at: datetime


class JobDetail(BaseModel):
    """A single job with the full offer text and, if it has one, its score."""

    id: int
    title: str
    company: str
    location: str
    url: str
    published_at: datetime | None
    salary: str | None
    description: str
    # None while the scorer has not reached this job yet.
    score: Score | None
