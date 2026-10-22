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
