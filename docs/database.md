# Database

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

Keyword matching has clear limits: full-text sources (Remotive) get more matches than snippet sources (Jooble), and it ignores context such as seniority or location. That is what the [Claude scorer](scoring.md) is for.
