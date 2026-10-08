#!/usr/bin/env bash
# Moniteur d'attaques en direct pour la journee pentest.
# Surligne : connexions reseau non reconnues, echecs d'authentification HTTP/MQTT,
# et scans de chemins sensibles. Trafic normal (Mac, ESP, conteneurs) ignore.
#
#   bash infra/scripts/watch-attacks.sh
#
# Ctrl-C pour arreter. Ne modifie rien, lecture seule.

set -u
cd "$(dirname "$0")/../.." || exit 1

R=$'\e[31m'; Y=$'\e[33m'; G=$'\e[32m'; DIM=$'\e[2m'; B=$'\e[1m'; N=$'\e[0m'

MAC_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "")
# IP reconnues : boucle locale, Mac sur le hotspot, reseau interne Docker.
ALLOW="127.0.0.1 ::1 localhost ${MAC_IP}"
# L'ESP est le client du port TLS 8883 ; appris automatiquement et affiche en vert.
ESP_IP=""

ts() { date +%H:%M:%S; }
n_alert=0; n_scan=0; n_auth=0

echo "${B}=== Moniteur SENTINEL-X : detection d'attaques ===${N}"
echo "${DIM}Mac=${MAC_IP:-?}  ports surveilles: 8080 (dashboard) 8010 (API) 1883/8883 (MQTT)${N}"
echo "${DIM}Vert=normal  Jaune=suspect  Rouge=attaque probable. Ctrl-C pour arreter.${N}"
echo

# --- Volet 1 : connexions reseau reelles vers les ports exposes (vraie IP peer) ---
# lsof a l'echelle de l'hote contourne le masquage d'IP de Docker.
seen_peers=""
watch_conns() {
  while true; do
    # Seules les lignes "com.docke" portent le socket d'ecoute du service :
    # NAME = IPlocale:PORTservice->IPpeer:PORTephemere. On en tire le port de
    # service (cote gauche) et la vraie IP du client (cote droit).
    conns=$(/usr/sbin/lsof -nP -iTCP:8080 -iTCP:8010 -iTCP:1883 -iTCP:8883 -sTCP:ESTABLISHED 2>/dev/null \
      | awk '$1 ~ /docke/ && $9 ~ /->/ {print $9}')
    while read -r name; do
      [ -z "$name" ] && continue
      local_side="${name%%->*}"; peer_side="${name##*->}"
      port="${local_side##*:}"                 # port de service
      ip="${peer_side%:*}"; ip="${ip#[}"; ip="${ip%]}"   # IP peer, crochets IPv6 retires
      case " 8080 8010 1883 8883 " in *" $port "*) ;; *) continue;; esac
      case " $ALLOW " in *" $ip "*) continue;; esac
      # Apprend l'ESP : client du port TLS 8883.
      if [ "$port" = "8883" ]; then
        if [ -z "$ESP_IP" ]; then ESP_IP="$ip"; ALLOW="$ALLOW $ip"
          echo "${G}$(ts) [ESP]   $ip reconnu comme boitier (MQTT TLS)${N}"; fi
        continue
      fi
      key="$ip:$port"
      case " $seen_peers " in *" $key "*) continue;; esac
      seen_peers="$seen_peers $key"
      svc=$([ "$port" = 8080 ] && echo dashboard || { [ "$port" = 8010 ] && echo API || echo MQTT-clair; })
      echo "${R}${B}$(ts) [CONNEXION INCONNUE] $ip -> port $port ($svc)${N}"
      n_alert=$((n_alert+1))
    done <<< "$conns"
    sleep 2
  done
}

# --- Volet 2 : journaux des services (echecs auth, scans de chemins) ---
SUSPECT='\.env|\.git|/admin|/wp-|/phpmyadmin|/config|/\.\.|/actuator|/vendor|/xmlrpc|passwd|/api/v1/commands|/setup|/console'
watch_logs() {
  docker compose logs -f --since=0s dashboard api mosquitto 2>/dev/null | while read -r line; do
    # Echec d'auth HTTP (401/403) : quelqu'un tente sans identifiants.
    if echo "$line" | grep -qE '" (401|403) '; then
      req=$(echo "$line" | grep -oE '"[A-Z]+ [^"]+"' | head -1)
      echo "${R}$(ts) [AUTH REFUSEE]  $req ${DIM}(acces protege, tentative sans cle/mot de passe)${N}"
      n_auth=$((n_auth+1)); continue
    fi
    # Scan de chemins sensibles (meme si 200/404).
    if echo "$line" | grep -qiE "$SUSPECT"; then
      req=$(echo "$line" | grep -oE '"[A-Z]+ [^"]+"' | head -1)
      [ -z "$req" ] && req="$line"
      echo "${Y}$(ts) [SCAN]  $req${N}"
      n_scan=$((n_scan+1)); continue
    fi
    # 404 en rafale = enumeration.
    if echo "$line" | grep -qE '" 404 '; then
      req=$(echo "$line" | grep -oE '"[A-Z]+ [^"]+"' | head -1)
      echo "${Y}$(ts) [404]   $req${N}"; continue
    fi
    # MQTT : auth refusee ou protocole invalide.
    if echo "$line" | grep -qiE "not authorised|unavailable|protocol|bad user"; then
      echo "${R}$(ts) [MQTT REFUSE]  ${line#*| }${N}"
      n_auth=$((n_auth+1)); continue
    fi
  done
}

cleaned=0
cleanup() {
  [ "$cleaned" = 1 ] && return; cleaned=1
  echo; echo "${B}=== Resume ===${N}"
  echo "  Connexions inconnues : ${n_alert}"
  echo "  Echecs d'auth        : ${n_auth}"
  echo "  Scans / 404          : ${n_scan}"
  kill 0 2>/dev/null
}
trap cleanup INT TERM

watch_conns &
watch_logs
