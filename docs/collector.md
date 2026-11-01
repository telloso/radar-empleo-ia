# Job collector

`collector/` fetches job offers from several sources, turns them into one common `Job` shape (`models.py`) and saves them in PostgreSQL (`db.py`).

| Source | What | Auth | Notes |
| --- | --- | --- | --- |
| [Remotive](https://github.com/remotive-io/remote-jobs-api) | Remote jobs | None | Max ~4 requests a day; jobs must link back to Remotive |
| [Jooble](https://es.jooble.org/api/about) | Jobs in Madrid | Free API key (`JOOBLE_API_KEY`) | `POST` with a JSON body; the key goes in the URL |

How it is built:

- **One adapter per source** (`sources/*.py`): each has `fetch_jobs()` and a `_to_job()` that maps the source's JSON to `Job`. Adding a source means one new module plus one line in `main.py`.
- **Resilient HTTP** (`http_utils.py`): timeouts, retries with exponential backoff on network errors, `429` and `5xx` (honouring `Retry-After`), and fail-fast on other `4xx`.
- **No leaked secrets**: API keys passed as `secret` are replaced with `***` in logs and error messages.
- **One broken source does not stop the others**; the exit code is `1` if any source failed, so a scheduler can notice.
- **Fails before spending API calls** if the database is unreachable.
- **Batch job, not a server**: the Compose service has no `restart` policy and sits behind the `jobs` profile, so `docker compose up` does not start it.

```bash
docker compose build collector
docker compose run --rm collector           # COLLECTOR_SEARCH in .env sets the keyword (default: python)
```

Tests (no network, `requests` and `time.sleep` are mocked):

```bash
cd collector
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -v
```
