#!/usr/bin/env bash
# Regénère infra/db/schema.sql depuis la base en cours (à relancer si models.py change).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
set -a; source "$ROOT/.env"; set +a
cd "$ROOT"
mkdir -p infra/db
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only --no-owner --no-privileges \
  | grep -vE '^(--|SET |SELECT pg_catalog|\\)' | grep -v '^$' > infra/db/schema.sql
echo "infra/db/schema.sql : $(grep -c '^CREATE TABLE' infra/db/schema.sql) tables"
