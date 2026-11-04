#!/bin/bash
# Read-only role for the API (api/): it can read jobs and scores, nothing else.
# Runs only on the first start; on an existing volume run it by hand:
#   docker compose exec db bash /docker-entrypoint-initdb.d/07-create-api-reader.sh
set -euo pipefail

# The password comes from .env through psql variables, so it never lives in the repo.
psql -v ON_ERROR_STOP=1 -v pw="$API_READER_PASSWORD" -v db="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE api_reader LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE :"db" TO api_reader;
GRANT USAGE ON SCHEMA public TO api_reader;
GRANT SELECT ON jobs, scores TO api_reader;
SQL
