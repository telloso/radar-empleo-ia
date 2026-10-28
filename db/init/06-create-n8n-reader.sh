#!/bin/bash
# Read-only role for n8n: it can read jobs and scores, nothing else.
# Runs only on the first start; on an existing volume run it by hand:
#   docker compose exec db bash /docker-entrypoint-initdb.d/06-create-n8n-reader.sh
set -euo pipefail

# The password comes from .env through psql variables, so it never lives in the repo.
psql -v ON_ERROR_STOP=1 -v pw="$N8N_READER_PASSWORD" -v db="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE n8n_reader LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE :"db" TO n8n_reader;
GRANT USAGE ON SCHEMA public TO n8n_reader;
GRANT SELECT ON jobs, scores TO n8n_reader;
SQL
