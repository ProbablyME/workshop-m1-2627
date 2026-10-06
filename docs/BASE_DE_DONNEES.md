# Base de données Sentinel-X (PostgreSQL 16)

## Où est le schéma

| Quoi                              | Où                                   |
|-----------------------------------|--------------------------------------|
| Définition de référence (ORM)     | `backend/app/models.py` (SQLAlchemy) |
| Création des tables               | automatique au démarrage de l'API (`Base.metadata.create_all`) |
| Export SQL du schéma réel         | `infra/db/schema.sql` (généré par `infra/scripts/db-schema-dump.sh`) |
| Données                           | volume Docker `pgdata`, jamais dans Git |

Il n'y a donc pas de script SQL à exécuter à la main : lancer `docker compose up` suffit.
`schema.sql` sert au dossier technique et aux outils externes.

## Tables

| Table         | Rôle                                               | Alimentée par                      |
|---------------|----------------------------------------------------|------------------------------------|
| `devices`     | état du boîtier (online, IP, firmware, last_seen)  | MQTT `status` + chaque message reçu |
| `telemetry`   | mesures toutes les 5 s (temp, hum, gaz, PIR, RSSI, heap) | MQTT `telemetry`, `POST /telemetry` |
| `alerts`      | franchissements de seuils, présence, pannes        | MQTT `alerts`, `POST /alerts`, IA  |
| `commands`    | ordres envoyés au boîtier (buzzer, LED)            | `POST /commands`                   |
| `detections`  | détections de la vision IA (label, confiance, bbox) | `POST /ai/detections`             |
| `predictions` | scores d'anomalie du modèle prédictif              | `POST /ai/predictions`             |

Toutes les tables ont un `id` auto-incrémenté et un `ts` horodaté en UTC par le serveur à la
réception. Index sur `ts` et `device_id` pour les séries temporelles.

## Ouvrir une console SQL

La base n'expose aucun port sur le laptop (choix de sécurité) : on y entre par le conteneur.

```bash
./infra/scripts/db-shell.sh                      # psql interactif
./infra/scripts/db-shell.sh -c "SELECT count(*) FROM telemetry;"
```

Pour un client graphique (DBeaver, pgAdmin, TablePlus), exposer temporairement le port en
ajoutant `ports: ["127.0.0.1:5432:5432"]` au service `db` du `docker-compose.yml`, puis
`docker compose up -d db`. Identifiants dans `.env` (`POSTGRES_*`). À retirer avant le pentest.

## Requêtes utiles

```sql
-- Dernière mesure
SELECT ts, temperature, humidity, gas_raw, motion, rssi, heap_free
FROM telemetry ORDER BY ts DESC LIMIT 1;

-- Moyennes par minute sur la dernière heure (courbes lissées, dossier)
SELECT date_trunc('minute', ts) AS minute,
       round(avg(temperature)::numeric, 2) AS temp,
       round(avg(humidity)::numeric, 1)    AS hum,
       round(avg(gas_raw))                  AS gaz
FROM telemetry
WHERE ts > now() - interval '1 hour'
GROUP BY 1 ORDER BY 1;

-- Alertes par type et sévérité
SELECT type, severity, state, count(*) FROM alerts GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- Jeu d'entraînement pour la maintenance prédictive (features brutes)
SELECT ts, temperature, humidity, gas_raw
FROM telemetry
WHERE temperature IS NOT NULL
ORDER BY ts;

-- Trous de télémétrie > 60 s (pertes de liaison)
SELECT ts AS reprise, lag(ts) OVER (ORDER BY ts) AS avant,
       ts - lag(ts) OVER (ORDER BY ts) AS duree
FROM telemetry
ORDER BY duree DESC NULLS LAST LIMIT 5;
```

## Volume et rétention

Une télémétrie toutes les 5 s = 17 280 lignes par jour, ≈ 2 Mo. Aucune purge nécessaire
sur la semaine du workshop. Pour vider la base sans toucher aux autres conteneurs :

```bash
docker compose down db && docker volume rm sentinel-x_pgdata && docker compose up -d
```
