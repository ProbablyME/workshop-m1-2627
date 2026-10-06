# Contrat de données Sentinel-X (Groupe 1)

Ce document est la référence unique pour les interfaces entre le boîtier
(ESP8266), le serveur (API Python), le dashboard (React) et les scripts IA.
Toute modification ici doit être répercutée dans le firmware, l'API et le dashboard.

## 1. Identifiants

| Élément        | Valeur             |
|----------------|--------------------|
| Groupe         | `g1`               |
| Device ID      | `SX-G1-01`         |
| Préfixe topics | `sentinel/g1/`     |

## 2. Topics MQTT

| Topic                    | Sens          | QoS | Retain | Fréquence                  |
|--------------------------|---------------|-----|--------|----------------------------|
| `sentinel/g1/telemetry`  | ESP → serveur | 0   | non    | toutes les 5 s             |
| `sentinel/g1/alerts`     | ESP → serveur | 1   | non    | sur changement d'état      |
| `sentinel/g1/status`     | ESP → serveur | 1   | oui    | connexion + LWT            |
| `sentinel/g1/cmd`        | serveur → ESP | 1   | non    | action superviseur         |
| `sentinel/g1/ai`         | IA → serveur  | 0   | non    | sur détection (optionnel)  |

Le script IA peut aussi parler directement à l'API en HTTP (voir §4), ce qui
est le chemin recommandé.

## 3. Payloads JSON

Tous les timestamps sont en millisecondes depuis le boot de l'ESP (`uptime_ms`)
ou en ISO 8601 UTC côté serveur. Le serveur horodate à réception.

### 3.1 `sentinel/g1/telemetry`

```json
{
  "device_id": "SX-G1-01",
  "uptime_ms": 123456,
  "temperature": 23.4,
  "humidity": 45.2,
  "gas_raw": 312,
  "gas_ppm": 180.5,
  "motion": false,
  "rssi": -61,
  "heap_free": 32768
}
```

| Champ         | Type   | Unité / plage                  | Capteur      |
|---------------|--------|--------------------------------|--------------|
| `temperature` | float  | °C, -40 à 80                   | DHT22        |
| `humidity`    | float  | %, 0 à 100                     | DHT22        |
| `gas_raw`     | int    | 0 à 1023 (ADC A0)              | MQ-2         |
| `gas_ppm`     | float  | estimation ppm, 0 si non calibré | MQ-2       |
| `motion`      | bool   | présence détectée              | PIR HC-SR501 |
| `rssi`        | int    | dBm                            | Wi-Fi        |
| `heap_free`   | int    | octets                         | ESP8266      |

### 3.2 `sentinel/g1/alerts`

Émis par l'ESP quand un seuil local est franchi ou qu'un état change.
Les seuils locaux servent d'alerte « réflexe » ; l'IA prédictive est côté serveur.

```json
{
  "device_id": "SX-G1-01",
  "uptime_ms": 123456,
  "type": "motion",
  "state": "on",
  "value": 1,
  "severity": "warning"
}
```

| Champ      | Valeurs                                        |
|------------|------------------------------------------------|
| `type`     | `motion`, `gas`, `temperature`, `humidity`, `sensor_fault` |
| `state`    | `on` (début) ou `off` (fin)                    |
| `severity` | `info`, `warning`, `critical`                  |
| `value`    | valeur mesurée ayant déclenché l'alerte        |

### 3.3 `sentinel/g1/status` (retained + Last Will)

```json
{ "device_id": "SX-G1-01", "online": true, "ip": "192.168.10.50", "fw": "0.1.0" }
```

Le Last Will publié par le broker à la déconnexion : `{"device_id":"SX-G1-01","online":false}`.

### 3.4 `sentinel/g1/cmd` (serveur → ESP)

```json
{ "actuator": "buzzer", "action": "on", "duration_ms": 2000, "cmd_id": "c-42" }
```

| Champ         | Valeurs                                             |
|---------------|-----------------------------------------------------|
| `actuator`    | `buzzer`, `led_red`, `led_green`, `led`, `camera` (intrusion vue par l'IA : `on`/`off`, le boîtier affiche « ALERTE CAMERA », allume la LED rouge et bipe) |
| `action`      | `on`, `off`, `blink`, `pulse`                       |
| `duration_ms` | optionnel, auto-extinction après N ms               |
| `cmd_id`      | identifiant de traçabilité, journalisé par l'ESP sur le port série |

Sémantique côté firmware : `on` sans durée reste manuel jusqu'à la prochaine commande ; `pulse` dure 1 s par défaut, `blink` 3 s ; **`off` rend la main au mode automatique** (LED verte = nominal, LED rouge = alerte ou liaison perdue) et coupe la sirène automatique. L'actionneur `led` applique l'action aux deux LED.

## 4. API REST (serveur, port 8000)

Base URL : `http://<ip-serveur>:8000/api/v1`

| Méthode | Route                    | Rôle                                                   |
|---------|--------------------------|--------------------------------------------------------|
| GET     | `/health`                | état API, broker, base                                 |
| POST    | `/alerts`                | **endpoint obligatoire du sujet**, réception d'une alerte |
| GET     | `/alerts?limit=50`       | historique des alertes                                 |
| GET     | `/telemetry/latest`      | dernière mesure                                        |
| GET     | `/telemetry?minutes=30`  | série temporelle récente                               |
| POST    | `/commands`              | envoie une commande à l'ESP (publie sur `/cmd`)        |
| GET     | `/commands?limit=20`     | historique des commandes                               |
| GET     | `/devices`               | état des boîtiers (online, ip, last_seen)              |
| POST    | `/ai/detections`         | le script vision pousse une détection                  |
| GET     | `/ai/detections?limit=20`| historique des détections                              |
| POST    | `/ai/predictions`        | le modèle prédictif pousse un score d'anomalie         |

Corps de `POST /alerts` : identique au payload §3.2, `device_id` obligatoire.
Corps de `POST /ai/detections` :

```json
{ "source": "yolo", "label": "person", "confidence": 0.87, "bbox": [120, 40, 300, 420], "frame_w": 640, "frame_h": 480 }
```

Corps de `POST /ai/predictions` :

```json
{ "model": "isolation_forest", "score": -0.21, "is_anomaly": true, "window_s": 300, "features": {"temp_slope": 0.12, "gas_slope": 3.4} }
```

Écriture protégée par l'en-tête `X-API-Key` (valeur dans `.env`, jamais commitée).

## 5. WebSocket (dashboard)

URL : `ws://<ip-serveur>:8000/ws`

Le serveur pousse des messages enveloppés :

```json
{ "kind": "telemetry" | "alert" | "status" | "command" | "detection" | "prediction", "ts": "2026-10-06T09:12:00Z", "data": { ... } }
```

Le dashboard ne publie rien sur le WebSocket ; les commandes passent par `POST /commands`.

## 6. Seuils locaux par défaut (firmware)

| Mesure      | Warning | Critical |
|-------------|---------|----------|
| Température | > 35 °C | > 45 °C  |
| Humidité    | > 80 %  | > 90 %   |
| Gaz (raw)   | ligne de base + 80 | ligne de base + 200 |

La ligne de base du gaz est mesurée par le boîtier après 3 min de chauffe du MQ-2 et suit la dérive lente du capteur. Ces seuils sont des garde-fous physiques. La détection fine (corrélation lente
température + gaz) est faite par l'IA côté serveur, conformément au sujet.
