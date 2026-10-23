-- How well each job matches my CV, as scored by the Claude API (collector/scorer.py).
-- Runs only on the first start; on an existing volume apply it by hand with psql.

CREATE TABLE IF NOT EXISTS scores (
    id             BIGSERIAL PRIMARY KEY,
    job_id         BIGINT      NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    -- Bumped when the prompt changes, so old and new scores can live side by side.
    prompt_version TEXT        NOT NULL,
    model          TEXT        NOT NULL,
    score          SMALLINT    NOT NULL CHECK (score BETWEEN 0 AND 100),
    fit            TEXT        NOT NULL CHECK (fit IN ('high', 'medium', 'low')),
    matched_skills TEXT[]      NOT NULL DEFAULT '{}',
    missing_skills TEXT[]      NOT NULL DEFAULT '{}',
    -- NULL when the offer does not say the salary.
    salary_ok      BOOLEAN,
    reasons        TEXT        NOT NULL,
    input_tokens   INTEGER     NOT NULL,
    output_tokens  INTEGER     NOT NULL,
    scored_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One score per job and prompt version: re-running the scorer pays nothing twice.
    UNIQUE (job_id, prompt_version)
);
