#!/bin/sh
# Dumps both databases and keeps a week of copies. They live on this same server: they
# protect against mistakes and bad runs, not against losing the server.
set -eu

backup_dir="$HOME/backups"
today=$(date +%F)
mkdir -p -m 700 "$backup_dir"
umask 077

# Write to a temporary name first, so a failed dump never looks like a good backup.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$backup_dir/radar-$today.tmp"
mv "$backup_dir/radar-$today.tmp" "$backup_dir/radar-$today.dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc n8n' > "$backup_dir/n8n-$today.tmp"
mv "$backup_dir/n8n-$today.tmp" "$backup_dir/n8n-$today.dump"

find "$backup_dir" -name '*.dump' -mtime +7 -delete
