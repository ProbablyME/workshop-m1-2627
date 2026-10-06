#!/usr/bin/env bash
# Prépare le PC Serveur Local en une commande :
#   1. crée .env depuis .env.example s'il n'existe pas (avec des secrets aléatoires)
#   2. génère la CA + le certificat serveur pour MQTTS
#   3. crée le fichier de mots de passe Mosquitto
# Usage : ./infra/scripts/bootstrap.sh <IP_DU_SERVEUR_SUR_LE_RESEAU_DE_TABLE>
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../.."
IP="${1:-}"
[[ -z "$IP" ]] && { echo "Usage: $0 <IP_DU_SERVEUR>" >&2; exit 1; }

cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "[bootstrap] création de .env avec des secrets aléatoires"
  gen() { openssl rand -hex 16; }
  sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(gen)/" \
      -e "s/^MQTT_PASSWORD=.*/MQTT_PASSWORD=$(gen)/" \
      -e "s/^API_KEY=.*/API_KEY=$(gen)/" \
      .env.example > .env
else
  echo "[bootstrap] .env existant conservé"
fi
# Clés ajoutées après coup (mise à jour d'un .env ancien)
grep -q '^DASHBOARD_PORT=' .env     || echo "DASHBOARD_PORT=8080" >> .env
grep -q '^DASHBOARD_USER=' .env     || echo "DASHBOARD_USER=superviseur" >> .env
grep -q '^DASHBOARD_PASSWORD=' .env || echo "DASHBOARD_PASSWORD=$(openssl rand -hex 8)" >> .env

if [[ ! -f infra/mosquitto/certs/server.crt ]]; then
  "$HERE/gen-certs.sh" "$IP"
else
  echo "[bootstrap] certificats existants conservés (supprimer infra/mosquitto/certs/* pour régénérer)"
fi

"$HERE/mqtt-passwd.sh"

# Mot de passe du dashboard (auth basic nginx)
set -a; source .env; set +a
mkdir -p infra/nginx
printf '%s:%s\n' "$DASHBOARD_USER" "$(openssl passwd -apr1 "$DASHBOARD_PASSWORD")" > infra/nginx/htpasswd
echo "[bootstrap] infra/nginx/htpasswd généré pour l'utilisateur $DASHBOARD_USER"
echo
echo "[bootstrap] terminé. Lancer :  docker compose up -d --build"
echo "[bootstrap] puis vérifier :    curl http://localhost:${API_PORT:-8000}/api/v1/health"
echo "[bootstrap] dashboard :         http://localhost:${DASHBOARD_PORT:-8080}  (utilisateur $DASHBOARD_USER, mot de passe dans .env)"
