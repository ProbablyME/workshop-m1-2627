# Firmware SENTINEL-X (ESP8266 NodeMCU Lolin v3)

Micrologiciel C++ (framework Arduino, PlatformIO) du boîtier. Lit DHT22, MQ-2 et PIR, affiche
l'état sur l'OLED, publie en MQTT(S) et exécute les commandes du dashboard (buzzer, LED).
Câblage : [docs/CABLAGE.md](../docs/CABLAGE.md). Interfaces : [docs/CONTRAT_DONNEES.md](../docs/CONTRAT_DONNEES.md).

## 1. Installer l'outillage

Trois façons équivalentes de compiler et flasher. Toutes reposent sur PlatformIO et partagent
le même `platformio.ini` ; choisir celle que l'on préfère, aucune n'est obligatoire.

### Option A : VS Code + extension « PlatformIO IDE » (la plus simple)

1. VS Code → Extensions → chercher « PlatformIO IDE » → Install (l'extension installe son propre Python et `pio`).
2. Fichier → Ouvrir le dossier → `firmware/`. Attendre la fin de l'initialisation (barre d'état en bas).
3. Barre d'état : icône ✓ = Build, → = Upload, prise = Serial Monitor.

### Option B : ligne de commande (CLI), sans aucun IDE

```bash
brew install platformio        # macOS ; ou : python3 -m pip install --user platformio
cd firmware
make build                     # compile
make upload                    # flashe (ESP en USB, bloc 7,5 V débranché)
make monitor                   # moniteur série 115200 bauds
```

Le `Makefile` trouve `pio` dans le PATH ou dans l'installation de l'extension VS Code.
Sous Windows sans `make` : `pio run`, `pio run -t upload`, `pio device monitor -b 115200`.

### Option C : CLion + plugin PlatformIO (méthode officielle des fiches EPSI)

Installeurs Windows dans `_Divers/` (JetBrains Toolbox, Python 3.14, `get-platformio.py`).
Fiche « Installation IDE IoT » : Toolbox → CLion → Plugins → « PlatformIO for CLion » → Open `firmware/`.
Inspections à désactiver : « Variable can be made constexpr » et « Proofreading → Typo ».

### Dans tous les cas : pilote USB et port série

- La Lolin v3 embarque un convertisseur **CH340**. macOS 12+ et Linux l'ont nativement.
  Windows : `_Divers/Windows10_CH340SER.zip` ou `Windows11_CH341SER.zip`.
- Repérer le port : `pio device list` (macOS `/dev/cu.usbserial-xxxx`, Windows « USB-SERIAL CH340 (COMx) »).
- Si la détection automatique échoue, renseigner `upload_port` / `monitor_port` dans `platformio.ini`
  ou passer `make upload PORT=COM5`.

## 2. Configurer les secrets

```bash
cp include/secrets.h.example include/secrets.h
```

Remplir `include/secrets.h` : SSID et mot de passe Wi-Fi, IP du serveur, identifiants MQTT
(ceux du `.env` du serveur) et l'empreinte du certificat affichée par `infra/scripts/gen-certs.sh`.
Pour la récupérer à tout moment :

```bash
openssl x509 -in infra/mosquitto/certs/server.crt -noout -fingerprint -sha1
```

`secrets.h` est dans `.gitignore`. Ne jamais le commiter.

## 3. Compiler, flasher, observer

```bash
cd firmware
make build        # ou : pio run
make upload       # ou : pio run -t upload      (ESP en USB, bloc 7,5 V débranché !)
make monitor      # ou : pio device monitor -b 115200
```

Sortie attendue au démarrage :

```
SENTINEL-X SX-G1-01  fw 0.1.0
[wifi] connexion a SENTINEL-G1..... OK 192.168.10.50
[mqtt] connexion 192.168.10.1:8883 (TLS)... OK
[mq2] R0 calibre = 9.12 kOhm        (après 60 s de chauffe)
```

## 3 bis. Mode banc d'essai (sans Wi-Fi)

`make bench-upload` flashe la variante `bench` : radio coupée dès le boot, pas de MQTT, et les
mesures sont tracées sur le port série toutes les 5 s (`[banc] T=.. H=.. gaz=.. pir=..`).
Pratique pour valider le câblage des capteurs et l'OLED sans réseau ni serveur. Revenir au
firmware complet avec `make upload`.

## 4. Comportement

| Événement                         | Firmware                                                       |
|-----------------------------------|----------------------------------------------------------------|
| Toutes les 2 s                    | lecture DHT22, moyenne de 8 échantillons MQ-2, état PIR        |
| Toutes les 5 s                    | publication `sentinel/g1/telemetry`                            |
| Seuil franchi (contrat §6)        | `sentinel/g1/alerts` state=on, escalade warning→critical, retour à off avec hystérésis |
| PIR passe à 1 / 0                 | alerte `motion` on / off, sirène 3 s                           |
| 3 lectures DHT22 ratées de suite  | alerte `sensor_fault`                                          |
| Alerte critique ou intrusion      | buzzer 3 s automatiquement, LED rouge tant que l'alerte dure   |
| Connexion MQTT                    | `status` retenu `online:true` + Last Will `online:false`       |
| Commande sur `sentinel/g1/cmd`    | `on` / `off` / `blink` / `pulse` avec `duration_ms` optionnel  |

LED verte = connecté et nominal. LED rouge = alerte active ou perte de liaison.
La commande `off` rend la main au mode automatique et coupe la sirène.

## 5. TLS : deux modes

| Mode                          | Avantage                                   | Contrainte                              |
|-------------------------------|--------------------------------------------|-----------------------------------------|
| **Empreinte SHA-1** (défaut)  | aucune horloge requise, fiable sur réseau isolé | à mettre à jour si le certificat change |
| **CA locale** (`MQTT_CA_CERT`)| chaîne complète, argument fort pour le jury | l'ESP a besoin de l'heure : NTP, sinon date de compilation (`BUILD_EPOCH`) |

Pour désactiver TLS en débogage : `TLS_ENABLED 0` et `MQTT_PORT 1883`. À ne jamais laisser pour la démo.

## 6. Dépannage

| Symptôme                              | Cause probable                                                     |
|---------------------------------------|--------------------------------------------------------------------|
| `[oled] introuvable a 0x3C`           | SDA/SCL inversés, ou module à 0x3D (changer `OLED_ADDR`)           |
| `rc=-2` à la connexion MQTT           | serveur injoignable : IP, port, pare-feu, ESP pas sur le bon Wi-Fi |
| `rc=-2` + `ssl=...` en TLS            | empreinte fausse ou certificat régénéré côté serveur               |
| `rc=5`                                | identifiants MQTT refusés (`infra/scripts/mqtt-passwd.sh`)         |
| `rc=-4`                               | timeout : heap insuffisant pour TLS, vérifier `heap` dans le log   |
| Redémarrages `wdt reset`              | alimentation faible (MQ-2 + Wi-Fi) ou GPIO de boot mal tiré        |
| Gaz toujours à 1023                   | pas de diviseur sur A0, ou MQ-2 AO relié à DO                      |
| DHT22 `pas de donnee`                 | DATA sur la mauvaise broche, ou lecture avant 2 s                  |
| Port série qui disparaît sur macOS (« Device not configured ») | pilote CH340 Apple : utiliser `make monitor`, ne pas forcer DTR/RTS dans un script maison ; sinon pilote WCH |
| Carte qui redémarre dès que le Wi-Fi démarre | alimentation trop faible : port USB direct ou hub alimenté ; en attendant, `make bench-upload` (sans radio) pour tester capteurs et OLED |
