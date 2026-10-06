#!/usr/bin/env bash
# Génère une CA locale + un certificat serveur pour Mosquitto (MQTTS 8883).
# Usage : ./infra/scripts/gen-certs.sh <IP_DU_SERVEUR> [jours]
# Les fichiers produits (infra/mosquitto/certs/*) ne sont PAS commités.
set -euo pipefail

SERVER_IP="${1:-}"
DAYS="${2:-365}"
if [[ -z "$SERVER_IP" ]]; then
  echo "Usage: $0 <IP_DU_SERVEUR> [jours]" >&2
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS="$HERE/../mosquitto/certs"
mkdir -p "$CERTS"
cd "$CERTS"

echo "[1/3] CA locale"
openssl req -x509 -new -nodes -newkey rsa:2048 -sha256 -days "$DAYS" \
  -subj "/C=FR/O=AetherCorp/OU=Sentinel-X G1/CN=Sentinel-X CA" \
  -keyout ca.key -out ca.crt

echo "[2/3] Clé + CSR serveur"
openssl req -new -nodes -newkey rsa:2048 -sha256 \
  -subj "/C=FR/O=AetherCorp/OU=Sentinel-X G1/CN=${SERVER_IP}" \
  -keyout server.key -out server.csr

cat > san.cnf <<CNF
subjectAltName = IP:${SERVER_IP}, DNS:mosquitto, DNS:localhost
extendedKeyUsage = serverAuth
CNF

echo "[3/3] Signature serveur par la CA"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days "$DAYS" -sha256 -extfile san.cnf
rm -f server.csr san.cnf

# Mosquitto tourne en uid 1883 dans le conteneur : la clé doit être lisible.
chmod 644 server.key ca.key

echo
echo "Empreinte SHA1 du certificat serveur (pour setFingerprint() côté ESP8266) :"
openssl x509 -in server.crt -noout -fingerprint -sha1 | sed 's/.*=//'
echo
echo "CA au format C (pour setTrustAnchors() côté ESP8266) : voir firmware/README.md"
echo "Fichiers générés dans $CERTS : ca.crt ca.key server.crt server.key"
