# Sentinel-X — Avant-poste industriel autonome (Groupe 1)

Prototype cyber-physique réalisé pour le Workshop EPSI M1 2026-27 « Mission Sentinel-X »
(AetherCorp Industrial Solutions). Un boîtier ESP8266 équipé de capteurs environnementaux
et de présence remonte ses données en MQTT chiffré vers un **PC Serveur Local** (option B :
laptop d'un apprenant) qui héberge la stack Docker, l'API, le dashboard de supervision et
l'IA de vision sur webcam USB.

## Architecture (option B)

```
                 Wi-Fi (sous-réseau de table 192.168.10.0/24)
                 (cible ; en démo, repli possible sur un hotspot partagé : seul MQTT_HOST change dans secrets.h)
┌────────────────────┐   MQTTS 8883 (TLS)   ┌──────────────────────────────────────────┐
│  Boîtier SENTINEL-X│ ───────────────────► │  PC Serveur Local (laptop)               │
│  ESP8266 NodeMCU   │ ◄─────────────────── │  ┌────────────┐  ┌──────┐  ┌──────────┐  │
│  DHT22 · MQ-2 · PIR│   sentinel/g1/cmd    │  │ Mosquitto  │─►│ API  │─►│ Postgres │  │
│  OLED · Buzzer · LED│                     │  └────────────┘  │FastAPI│ └──────────┘  │
└────────────────────┘                      │        ▲         └──┬───┘               │
                                            │        │            │ WebSocket + REST   │
                      Webcam USB ──────────►│  ┌─────┴─────┐  ┌───▼──────────────┐     │
                                            │  │ IA vision │  │ Dashboard React  │     │
                                            │  │ + prédictif│  │ (supervision)    │     │
                                            │  └───────────┘  └──────────────────┘     │
                                            └──────────────────────────────────────────┘
```

Détails : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Interfaces entre blocs :
[docs/CONTRAT_DONNEES.md](docs/CONTRAT_DONNEES.md) (référence unique pour les 4 filières).
Montage électronique : [docs/CABLAGE.md](docs/CABLAGE.md). Boîtier et Fablab : [docs/BOITIER.md](docs/BOITIER.md).
Base de données (schéma, console SQL, requêtes) : [docs/BASE_DE_DONNEES.md](docs/BASE_DE_DONNEES.md).

## Structure du dépôt

| Dossier      | Filière | Contenu                                                        | État        |
|--------------|---------|----------------------------------------------------------------|-------------|
| `firmware/`  | DEV     | Firmware ESP8266 C++ (PlatformIO / CLion) : capteurs, OLED, MQTTS, commandes | **fait** |
| `backend/`   | DEV     | API FastAPI : MQTT ↔ PostgreSQL ↔ WebSocket, `POST /api/v1/alerts` | **fait** |
| `dashboard/` | DEV     | Interface React (tuiles, courbes temps réel, alertes, commandes, IA) | **fait** |
| `ai/`        | IA      | Vision YOLOv8n (intrusion + flux vidéo) et maintenance prédictive Isolation Forest | **fait** |
| `infra/`     | INFRA   | Config Mosquitto (TLS), scripts certificats / mots de passe / bootstrap | **fait** |
| `docs/`      | tous    | Contrat de données, architecture, câblage, boîtier, matrice de sécurité, rapport d'audit | en cours |
| `fablab/`    | tous    | Plaque de gravure laser (SVG), exports Fusion360 à venir        | en cours    |

## Démarrage rapide (PC Serveur Local)

Prérequis : Docker Desktop (ou Docker Engine + Compose v2), OpenSSL, Python 3.12+.

```bash
# 1. Génère .env (secrets aléatoires), la CA + le certificat MQTTS, le fichier de mots de passe
./infra/scripts/bootstrap.sh 192.168.10.1        # ← IP du laptop sur le réseau de table

# 2. Construit et lance Mosquitto + PostgreSQL + API
docker compose up -d --build

# 3. Vérifie
curl http://localhost:8000/api/v1/health
# → {"status":"ok","mqtt_connected":true,"db_ok":true,"ws_clients":0,"version":"0.1.0"}
```

Documentation interactive de l'API : http://localhost:8000/docs
Dashboard de supervision : http://localhost:8080 (utilisateur et mot de passe `DASHBOARD_*` du `.env`).

Si le port 8000 est déjà pris sur la machine, définir `API_PORT=8010` (ou autre) dans `.env`.

## Tester sans le boîtier physique

Un simulateur publie de la télémétrie et des alertes réalistes sur le broker :

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python backend/tools/simulate_esp.py --period 2 --intrusion      # MQTT 1883
backend/.venv/bin/python backend/tools/simulate_esp.py --tls --drift               # MQTTS 8883, dérive lente temp+gaz
```

Puis :

```bash
curl http://localhost:8000/api/v1/telemetry/latest
curl -X POST http://localhost:8000/api/v1/commands \
     -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
     -d '{"actuator":"buzzer","action":"pulse","duration_ms":1500}'
```

## Lancer l'IA (hors Docker, sur le laptop serveur)

```bash
cd ai && /opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python vision.py          # webcam → YOLOv8n, alerte intrusion, flux http://localhost:8001/stream
.venv/bin/python predict.py         # Isolation Forest sur la télémétrie, score toutes les 30 s
```

Détails dans [ai/README.md](ai/README.md).

## Développer le dashboard (hors Docker)

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173, proxifie /api et /ws vers l'API du .env (API_PORT)
npm run build        # build de production dans dist/, servi par nginx dans Docker
```

Le serveur Vite et nginx injectent tous deux l'en-tête `X-API-Key` côté serveur : la clé
n'apparaît jamais dans le code livré au navigateur. `?theme=dark` ou `?theme=light` dans l'URL
force le thème (utile pour l'écran du jury).

## Lancer l'API hors Docker (dev)

```bash
cd backend
DATABASE_URL=sqlite:///./sentinel-dev.db MQTT_HOST=localhost API_KEY=dev \
  .venv/bin/uvicorn app.main:app --reload --port 8000
```

Sans broker joignable, l'API démarre quand même (health en `degraded`) et les routes HTTP
restent utilisables, ce qui suffit pour développer le dashboard.

## Endpoints principaux

| Méthode | Route                           | Rôle                                             |
|---------|---------------------------------|--------------------------------------------------|
| GET     | `/api/v1/health`                | état API / broker / base                         |
| POST    | `/api/v1/alerts`                | **endpoint obligatoire du sujet**                |
| GET     | `/api/v1/alerts`                | historique des alertes                           |
| GET     | `/api/v1/telemetry/latest`      | dernière mesure                                  |
| GET     | `/api/v1/telemetry?minutes=30`  | série temporelle                                 |
| POST    | `/api/v1/commands`              | pilote buzzer / LED via MQTT                     |
| GET     | `/api/v1/devices`               | état du boîtier (online, IP, firmware)           |
| POST    | `/api/v1/ai/detections`         | détections de la vision IA                       |
| POST    | `/api/v1/ai/predictions`        | scores d'anomalie du modèle prédictif            |
| WS      | `/ws`                           | flux temps réel pour le dashboard                |

Les écritures exigent l'en-tête `X-API-Key` (valeur `API_KEY` du `.env`).

## Sécurité

- **Aucun secret dans le dépôt** : `.env`, `infra/mosquitto/passwd`, `infra/mosquitto/certs/`
  et `firmware/include/secrets.h` sont ignorés par Git. Les secrets sont générés par `bootstrap.sh`.
- **MQTTS** : listener 8883 avec CA locale ; l'ESP8266 vérifie le serveur (CA ou empreinte SHA-1
  affichée par `gen-certs.sh`). Authentification login/mot de passe obligatoire (`allow_anonymous false`).
- Le listener 1883 en clair ne sert qu'au debug sur la table ; le fermer (UFW) avant le pentest.
- PostgreSQL n'expose aucun port sur l'hôte. L'API tourne sans privilège root dans son conteneur.
- Limites Mosquitto (`max_connections`, `max_queued_messages`, `max_packet_size`) contre le flood.
- Mosquitto avertit que `passwd` est lisible par tous (`644`) : nécessaire pour que le conteneur
  (uid 1883) le lise via le bind mount ; le fichier est hors Git.
- Hardening de l'hôte (UFW, SSH par clés, Docker) : voir `docs/` (à compléter jeudi).

## Jour de démo : maintien en condition opérationnelle

- Empêcher la veille du laptop serveur pendant la démo : `caffeinate -dims` dans un terminal, ou
  Réglages Système → Batterie → ne jamais mettre en veille sur secteur. Constaté le 5 octobre :
  98 minutes sans télémétrie pendant une veille du Mac, le boîtier s'est reconnecté seul au réveil.
- Laptop sur secteur, Wi-Fi de table en 2,4 GHz, `docker compose ps` tout en `healthy` avant de passer.
- Surveiller `heap_free` dans la télémétrie : ≈ 17,6 Ko après la session TLS, alerter sous 10 Ko.

## Équipe & conventions

- Groupe 1 — livrables nommés `Workshop2026-M1-G1-*`.
- Commits sémantiques : `feat(firmware): …`, `fix(api): …`, `docs: …`, `infra: …`.
- Toute modification d'interface passe d'abord par `docs/CONTRAT_DONNEES.md`.
