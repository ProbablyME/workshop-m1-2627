#!/usr/bin/env bash
# Console psql dans le conteneur PostgreSQL (identifiants lus dans .env).
# Usage : ./infra/scripts/db-shell.sh            (interactif)
#         ./infra/scripts/db-shell.sh -c "SELECT count(*) FROM telemetry;"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
set -a; source "$ROOT/.env"; set +a
cd "$ROOT"
if [[ $# -eq 0 ]]; then
  docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
else
  docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
fi
