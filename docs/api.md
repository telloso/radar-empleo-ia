# HTTP API (FastAPI)

`api/` is a small read-only web API over the Radar database, so any program (a browser, n8n, a script) can ask for the best jobs as JSON instead of opening `psql`. It is built with [FastAPI](https://fastapi.tiangolo.com/), served by Uvicorn, and reads the database through SQLAlchemy.

| Endpoint | Returns |
| --- | --- |
| `GET /health` | `{"status": "ok"}` if the API process is up (does not touch the database) |
| `GET /jobs/top?limit=10&fit=medium` | The best scored jobs, highest score first. `limit` 1-50 (default 10), `fit` optional: `high`, `medium` or `low` |
| `GET /jobs/{job_id}` | One job with its full description and its latest score (`score` is `null` while it has none), or `404` |
| `GET /docs` | Interactive documentation generated from the code, where every endpoint can be tried |

```bash
docker compose up -d --build api     # name the service: a plain "up" would also start n8n
curl "http://localhost:8000/jobs/top?limit=1"
```

```json
[
  {"id": 13, "title": "Desarrollador/a Python ID82555", "company": "AgileEngine, LLC.",
   "location": "Madrid", "url": "https://es.jooble.org/jdp/-1656766814214570271",
   "published_at": "2026-10-21T14:58:44.730000Z", "score": 62, "fit": "medium"}
]
```

## How a request flows

1. Uvicorn receives the HTTP request and hands it to FastAPI.
2. FastAPI validates the parameters against the type hints: `limit` must be an integer from 1 to 50 and `fit` one of three values, or the answer is `422` and the endpoint never runs.
3. The endpoint asks for a `JobRepository` through dependency injection (`Depends(get_repository)`): one SQLAlchemy session per request, whose pooled connection goes back to the pool when the response is built.
4. The repository runs the query and returns Pydantic models (`api/schemas.py`); FastAPI checks the response against them and turns it into JSON.

## Design choices

- **Its own service and image, apart from `collector/`.** The jobs run once and exit; the API is a server that stays up. Its image also leaves out the embedding model, about 220 MB the API does not need.
- **Read-only database role.** The API connects as `api_reader` (`db/init/07-create-api-reader.sh`), which can only `SELECT` from `jobs` and `scores`. Even a bug in the API cannot change data. The container also runs as a non-root user, and its port is bound to `127.0.0.1`.
- **Same score as the Telegram digest.** A job can have several scores (one per prompt version); like the digest, the API uses the newest one (`DISTINCT ON (job_id) ... ORDER BY scored_at DESC`), so both always show the same number.
- **Repository pattern.** Every query lives in `JobRepository` (`api/db.py`); the endpoints only call its two methods. That is what let the data layer move from raw SQL with psycopg to SQLAlchemy without touching the endpoints or the tests, and it is what the tests replace.
- **SQLAlchemy here, raw SQL elsewhere.** The API's queries are ordinary filters and joins, which the ORM builds step by step (an optional filter is an `if`) and gives a connection pool. The scorer, the embedder and the RAG searches keep their hand-written SQL, where it is clearer, for example the vector search with pgvector. The tables are still created by the SQL files in `db/init/`: `api/models.py` only maps them, so there are no migrations.
- **Clear errors.** An unreachable database answers `503 Database unavailable` instead of a `500` with a traceback. SQLAlchemy wraps the driver's errors in its own, so `db.py` names the one to catch (`DatabaseUnavailable`) and `main.py` does not depend on the library.
- **`def`, not `async def`.** The database calls are blocking, so the endpoints are plain functions and FastAPI runs each one in a worker thread. An `async def` endpoint with a blocking driver would freeze the whole server during a slow query.

## Tests

```bash
cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -v
```

The 11 tests in `api/tests/test_main.py` cover the HTTP layer: defaults, parameters passed to the repository, the four kinds of invalid input (`422`, without reaching the database), the nested score, `404`, route order (`/jobs/top` must not be read as a job id) and `503`. They swap the repository for a fake one with `app.dependency_overrides`, so they need no database and run in under a second.

The queries themselves were checked against the real database: the SQLAlchemy version returns exactly the same JSON as the earlier raw SQL version for the top jobs, every fit filter and every job detail.

## Limits worth knowing

- **No authentication.** It is only reachable from the same machine (`127.0.0.1`), and it only reads; exposing it to the internet would need a token or an API gateway in front first.
- **Runs locally, not on the VPS yet.** The deploy playbook only starts `db` and `n8n`.
- **No pagination.** `limit` caps a response at 50 jobs, which is enough for a few hundred stored jobs.
- **The tests do not cover the SQL.** The queries were checked by hand against real data; integration tests against a throwaway Postgres would be the next step.
