-- Skills from my CV, used to rank jobs by plain keyword matching (see db/queries.sql).
-- Runs only on the first start; on an existing volume apply it by hand with psql.

CREATE TABLE IF NOT EXISTS skills (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO skills (name) VALUES
    ('Python'), ('SQL'), ('PostgreSQL'), ('Docker'), ('Linux'), ('Bash'),
    ('Git'), ('API'), ('REST'), ('n8n'), ('LLM'), ('IA'), ('AI')
ON CONFLICT (name) DO NOTHING;
