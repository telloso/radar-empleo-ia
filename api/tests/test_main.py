"""HTTP layer tests: validation, status codes, JSON shape and route order.

The real repository is swapped for a fake one through FastAPI's dependency_overrides,
so these tests need no database and run in milliseconds.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import db
from main import app, get_repository
from schemas import JobDetail, JobSummary, Score

NOW = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)

SUMMARY = JobSummary(
    id=39, title="AI Engineer", company="Quest Global", location="Madrid",
    url="https://example.com/39", published_at=NOW, score=82, fit="high",
)

DETAIL = JobDetail(
    **SUMMARY.model_dump(exclude={"score", "fit"}),
    salary=None,
    description="Python, FastAPI and SQLAlchemy.",
    score=Score(
        score=82, fit="high", salary_ok=None, matched_skills=["Python"],
        missing_skills=["SQLAlchemy"], reasons="Good fit.", model="claude-haiku-5-5",
        scored_at=NOW,
    ),
)


class FakeRepository:
    """Stands in for db.JobRepository and remembers how it was called."""

    def __init__(self) -> None:
        self.top_calls: list[tuple[int, str | None]] = []

    def top_jobs(self, limit: int, fit: str | None = None) -> list[JobSummary]:
        self.top_calls.append((limit, fit))
        return [SUMMARY]

    def get_job(self, job_id: int) -> JobDetail | None:
        return DETAIL if job_id == 39 else None


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def client(repo: FakeRepository):
    app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_top_jobs_uses_defaults(client: TestClient, repo: FakeRepository) -> None:
    response = client.get("/jobs/top")
    assert response.status_code == 200
    assert response.json()[0]["company"] == "Quest Global"
    assert repo.top_calls == [(10, None)]


def test_top_jobs_passes_limit_and_fit(client: TestClient, repo: FakeRepository) -> None:
    client.get("/jobs/top", params={"limit": 3, "fit": "high"})
    assert repo.top_calls == [(3, "high")]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 51}, {"limit": "abc"}, {"fit": "great"}])
def test_top_jobs_rejects_invalid_params(
    client: TestClient, repo: FakeRepository, params: dict
) -> None:
    response = client.get("/jobs/top", params=params)
    assert response.status_code == 422
    # Rejected by FastAPI before the endpoint runs: the database is never asked.
    assert repo.top_calls == []


def test_get_job_returns_nested_score(client: TestClient) -> None:
    response = client.get("/jobs/39")
    assert response.status_code == 200
    assert response.json()["score"]["model"] == "claude-haiku-5-5"


def test_get_job_not_found(client: TestClient) -> None:
    response = client.get("/jobs/99999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_top_route_is_not_taken_as_a_job_id(client: TestClient, repo: FakeRepository) -> None:
    # If /jobs/{job_id} were declared first, this would be a 422 ("top" is not an int).
    assert client.get("/jobs/top").status_code == 200
    assert len(repo.top_calls) == 1


def test_database_down_returns_503() -> None:
    def broken_repository():
        raise db.DatabaseUnavailable("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_repository] = broken_repository
    try:
        response = TestClient(app).get("/jobs/top")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
