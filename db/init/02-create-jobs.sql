-- Job offers collected from every source, one row per offer.
-- Runs only on the first start (in the POSTGRES_DB database, "radar");
-- on an existing volume apply it by hand with psql.

CREATE TABLE IF NOT EXISTS jobs (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    external_id   TEXT        NOT NULL,
    title         TEXT        NOT NULL,
    company       TEXT        NOT NULL,
    location      TEXT        NOT NULL DEFAULT '',
    url           TEXT        NOT NULL,
    published_at  TIMESTAMPTZ,
    salary        TEXT,
    description   TEXT        NOT NULL DEFAULT '',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The same offer comes back on every run: this is what keeps it to one row.
    UNIQUE (source, external_id)
);
