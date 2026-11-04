"""Read-only HTTP API over the Radar database: the best jobs and the detail of one.

Run it locally with `uvicorn main:app --reload` and open http://localhost:8000/docs.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

import db
from schemas import Fit, JobDetail, JobSummary

app = FastAPI(
    title="Radar de empleo API",
    description="Jobs collected by the Radar and scored against my CV by Claude.",
    version="1.0.0",
)


def get_repository() -> Iterator[db.JobRepository]:
    """Dependency: one session per request, closed once the response is built
    (its connection goes back to the pool)."""
    with db.connect() as session:
        yield db.JobRepository(session)


# Any endpoint with a parameter of this type gets a repository from get_repository.
Repository = Annotated[db.JobRepository, Depends(get_repository)]


@app.exception_handler(db.DatabaseUnavailable)
def database_unavailable(request: Request, exc: db.DatabaseUnavailable) -> JSONResponse:
    """Database down or unreachable: answer 503 instead of a bare 500 with a traceback."""
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: the API process is up (it does not touch the database)."""
    return {"status": "ok"}


# Declared before /jobs/{job_id}: routes are matched in order, and "top" would
# otherwise be read as a job_id (and rejected with 422 because it is not an int).
@app.get("/jobs/top")
def top_jobs(
    repo: Repository,
    limit: Annotated[int, Query(ge=1, le=50, description="How many jobs to return")] = 10,
    fit: Annotated[Fit | None, Query(description="Only jobs with this fit")] = None,
) -> list[JobSummary]:
    """Best scored jobs, highest score first."""
    return repo.top_jobs(limit=limit, fit=fit)


@app.get("/jobs/{job_id}", responses={404: {"description": "Job not found"}})
def get_job(job_id: int, repo: Repository) -> JobDetail:
    """One job with its full description and its latest score."""
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
