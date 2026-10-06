#!/usr/bin/env bash
# Crée/MAJ le fichier de mots de passe Mosquitto à partir du .env (MQTT_USER / MQTT_PASSWORD).
# Usage : ./infra/scripts/mqtt-passwd.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../.."
set -a; source "$ROOT/.env"; set +a
: "${MQTT_USER:?MQTT_USER manquant dans .env}"
: "${MQTT_PASSWORD:?MQTT_PASSWORD manquant dans .env}"
PASSWD="$ROOT/infra/mosquitto/passwd"
touch "$PASSWD"
docker run --rm -v "$PASSWD:/passwd" eclipse-mosquitto:2.0 \
  mosquitto_passwd -b /passwd "$MQTT_USER" "$MQTT_PASSWORD"
echo "Fichier $PASSWD mis à jour pour l'utilisateur $MQTT_USER"
