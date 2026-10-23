# radar-empleo-ia

AI-powered job radar: collects job offers, stores them in PostgreSQL, scores them against my CV with the Claude API, answers questions about them (RAG) and sends a daily digest to Telegram via n8n.

> Work in progress. This README will grow as each part is built.

## Planned stack

- **Python** — job collection scripts
- **PostgreSQL** — storage and querying
- **Claude API** — scoring with structured output, RAG
- **n8n** — daily Telegram digest
- **Docker Compose** — local environment
- **Terraform + Ansible** — deployment to a VPS

## Architecture (current)

```mermaid
flowchart LR
    subgraph compose["Docker Compose network"]
        collector["collector<br/>(Python, run on demand)"]
        scorer["scorer<br/>(Python, run on demand)"]
        db[("PostgreSQL 17<br/>databases: radar, n8n")]
        n8n["n8n 2.43"]
    end
    collector -- "host: db<br/>upsert into jobs" --> db
    db -- "unscored jobs" --> scorer
    scorer -- "insert into scores" --> db
    scorer -- "profile + job" --> claude(["Claude API<br/>Opus 5.5"])
    claude -- "JSON score" --> scorer
    remotive(["Remotive API<br/>remote jobs"]) --> collector
    jooble(["Jooble API<br/>jobs in Madrid"]) --> collector
    n8n -- "host: db" --> db
    db --- pgdata[("volume: pgdata")]
    n8n --- n8ndata[("volume: n8n_data")]
    you(["localhost"]) -- ":5432" --> db
    you -- ":5678" --> n8n
```

- Services find each other by name on the Compose network (`db`), so no IPs are hard-coded.
- Data lives in named volumes and survives `docker compose down` (but not `down -v`).
- Ports are bound to `127.0.0.1` only, so nothing is exposed to the local network.
- Secrets come from a git-ignored `.env`; `.env.example` lists the variables.

## Getting started

Requirements: Docker with Docker Compose.

```bash
cp .env.example .env          # then fill in the values
docker compose up -d          # start PostgreSQL and n8n
docker compose ps             # both should be "Up"; db should be "healthy"
```

- n8n: http://localhost:5678
- PostgreSQL: `docker compose exec db psql -U <user> -d <db>`
- Collector: `docker compose run --rm collector` (see below)
- Scorer: `docker compose run --rm scorer` (see below)

## Job collector

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

## Database

The `radar` database holds the jobs. Tables are created by `db/init/*.sql` on the first start of an empty volume; on an existing volume, apply a new script by hand:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init/02-create-jobs.sql
```

- **`jobs`**: one row per offer. `UNIQUE (source, external_id)` identifies an offer, so the collector saves with an upsert (`INSERT … ON CONFLICT … DO UPDATE`): running it twice gives the same rows, it only refreshes their data and `last_seen_at`. `first_seen_at` keeps when the offer first appeared.
- **Transactions**: each source is saved in one transaction, so a failure never leaves half a batch.
- **Parameterised queries**: values are sent apart from the SQL (`%(name)s`), which prevents SQL injection.
- **`skills`**: skills from my CV, used as a keyword-matching baseline before LLM scoring.

`db/queries.sql` has example queries: recent jobs in Madrid, jobs with a salary, companies hiring for several roles, and jobs ranked by how many of my skills they mention (a `JOIN` on a regex with word boundaries).

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries.sql
```

Keyword matching has clear limits: full-text sources (Remotive) get more matches than snippet sources (Jooble), and it ignores context such as seniority or location. That is what the [Claude scorer](#job-scoring-with-claude) is for.

## Job scoring with Claude

`collector/scorer.py` rates every job against my profile with the Claude API and saves the result in the `scores` table (`db/init/04-create-scores.sql`).

How it works:

1. **Only new work**: it reads the jobs that have no score for the current `PROMPT_VERSION` (`LEFT JOIN scores … WHERE s.job_id IS NULL`). Running it twice costs nothing the second time; `UNIQUE (job_id, prompt_version)` backs this up in the database.
2. **Prompt**: the system prompt holds my profile and a scoring rubric (what 80, 60 and 40 mean, and what weighs most); the job goes in the user message inside `<job_offer>` tags, marked as third-party data so instructions inside a job posting are ignored (prompt injection).
3. **Structured output**: `client.messages.parse()` with a Pydantic model (`JobScore`). The API constrains the answer to that JSON schema and the SDK validates it, so every field maps straight to a column: `score` (0-100), `fit` (`high`/`medium`/`low`), `matched_skills`, `missing_skills`, `salary_ok` (`NULL` when the job does not say) and `reasons`. `CHECK` constraints on the table are a second line of defence.
4. **Errors**: the SDK retries `429` and `5xx` with exponential backoff; a job that still fails is logged and skipped (it is retried on the next run); a rejected API key stops the run. Each score is committed on its own, so a crash never loses scores already paid for.
5. **Cost tracking**: input and output tokens are stored per job. Scoring the first 40 jobs with Claude Opus 5.5 cost $0.80, about 2 cents a job (query 6 in `db/queries.sql`).

The profile is personal data: `collector/profile.md` is git-ignored and kept out of the image (it is mounted read-only into the container). Copy `collector/profile.example.md` to start your own.

```bash
docker compose build scorer
docker compose run --rm scorer             # needs ANTHROPIC_API_KEY in .env
# or locally, scoring a single job as a cheap test:
cd collector && set -a && source ../.env && set +a && SCORER_LIMIT=1 .venv/bin/python scorer.py
```

Limits worth knowing:

- Jooble returns a snippet, not the full job description, so those scores rest on less information (the reasons say so when it matters).
- On jobs I had already assessed by hand, the scores agreed with my own judgment (for example, a mid-level "AI Engineer Python" role scored 62, `medium`), but 40 jobs is a small sample.
- No prompt caching: the profile plus rubric is around 1,000 tokens, below the minimum cacheable size for this model.

## Status

- [x] Block 1: repository and Git setup
- [x] Block 2: Docker — collector image, PostgreSQL and n8n with Docker Compose
- [x] Block 3: Python — job collector (Remotive + Jooble) with retries, Compose service and tests
- [x] Block 4: SQL — jobs stored in PostgreSQL without duplicates, queries with filters and a JOIN
- [x] Block 5: Claude API — jobs scored against my CV with structured output
