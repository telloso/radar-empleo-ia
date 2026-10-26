-- Useful queries over the collected jobs. Run them all with:
--   docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries.sql

-- 1. Jobs in Madrid published in the last 7 days, newest first.
SELECT left(title, 50) AS title, company, published_at::date AS published
FROM jobs
WHERE location ILIKE '%madrid%'
  AND published_at > now() - interval '7 days'
ORDER BY published_at DESC
LIMIT 10;

-- 2. Jobs that publish a salary.
SELECT left(title, 50) AS title, company, salary
FROM jobs
WHERE salary IS NOT NULL;

-- 3. Companies with more than one open job.
SELECT company, count(*) AS jobs
FROM jobs
GROUP BY company
HAVING count(*) > 1
ORDER BY jobs DESC;

-- 4. Jobs ranked by how many of my skills they mention (JOIN on a condition).
--    \m and \M are word boundaries, so 'API' does not match 'capital'.
SELECT left(j.title, 50) AS title,
       j.company,
       count(*) AS matches,
       string_agg(s.name, ', ' ORDER BY s.name) AS skills
FROM jobs AS j
JOIN skills AS s
  ON j.title || ' ' || j.description ~* ('\m' || s.name || '\M')
WHERE j.title NOT ILIKE '%senior%'
GROUP BY j.id
ORDER BY matches DESC, j.published_at DESC
LIMIT 10;

-- 5. Best matches according to Claude (see collector/scorer.py), with the reasons.
SELECT s.score, s.fit, s.salary_ok, left(j.title, 45) AS title, j.company, s.reasons
FROM scores AS s
JOIN jobs AS j ON j.id = s.job_id
WHERE s.prompt_version = 'v1'
  AND s.fit IN ('high', 'medium')
ORDER BY s.score DESC
LIMIT 10;

-- 6. What each scoring run cost, in US dollars (Claude Opus 5.5: $4 per million
--    input tokens, $20 per million output tokens).
SELECT prompt_version, model, count(*) AS jobs,
       round(sum(input_tokens) * 4.0 / 1e6 + sum(output_tokens) * 20.0 / 1e6, 2) AS usd
FROM scores
GROUP BY prompt_version, model;

-- 7. Jobs most similar in meaning to job 39 (Quest Global), by embeddings.
--    <=> is pgvector's cosine distance: 0 = same meaning, 2 = opposite.
--    DISTINCT ON keeps only the closest chunk of each job, so one long offer
--    with many chunks cannot fill the whole top 5 by itself.
WITH query AS (
    SELECT embedding FROM job_chunks WHERE job_id = 39 AND chunk_index = 0
),
best_chunk AS (
    SELECT DISTINCT ON (c.job_id)
           c.job_id, c.chunk_index, c.embedding <=> q.embedding AS distance
    FROM job_chunks AS c, query AS q
    WHERE c.job_id <> 39
    ORDER BY c.job_id, distance
)
SELECT round(b.distance::numeric, 3) AS distance, b.job_id, b.chunk_index,
       left(j.title, 50) AS title, j.company
FROM best_chunk AS b
JOIN jobs AS j ON j.id = b.job_id
ORDER BY b.distance
LIMIT 5;
