# Job scoring with Claude

`collector/scorer.py` rates every job against my profile with the Claude API and saves the result in the `scores` table (`db/init/04-create-scores.sql`).

How it works:

1. **Only new work**: it reads the jobs that have no score for the current `PROMPT_VERSION` (`LEFT JOIN scores … WHERE s.job_id IS NULL`). Running it twice costs nothing the second time; `UNIQUE (job_id, prompt_version)` backs this up in the database.
2. **Prompt**: the system prompt holds my profile and a scoring rubric (what 80, 60 and 40 mean, and what weighs most); the job goes in the user message inside `<job_offer>` tags, marked as third-party data so instructions inside a job posting are ignored (prompt injection).
3. **Structured output**: `client.messages.parse()` with a Pydantic model (`JobScore`). The API constrains the answer to that JSON schema and the SDK validates it, so every field maps straight to a column: `score` (0-100), `fit` (`high`/`medium`/`low`), `matched_skills`, `missing_skills`, `salary_ok` (`NULL` when the job does not say) and `reasons`. `CHECK` constraints on the table are a second line of defence.
4. **Errors**: the SDK retries `429` and `5xx` with exponential backoff; a job that still fails is logged and skipped (it is retried on the next run); a rejected API key stops the run. Each score is committed on its own, so a crash never loses scores already paid for.
5. **Cost tracking**: input and output tokens are stored per job. Scoring the first 40 jobs with Claude Opus 5.5 cost $0.80, about 2 cents a job (query 6 in `db/queries.sql`).
6. **Daily limit**: `SCORER_LIMIT` (default 10) caps each run, newest jobs first, so a day with many new offers cannot empty the API balance. The rest wait for later runs.

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
