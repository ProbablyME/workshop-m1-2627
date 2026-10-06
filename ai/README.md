# IA locale Sentinel-X

Deux scripts Python qui tournent sur le PC Serveur Local, hors Docker, pour accéder à la
webcam USB et aux ressources CPU/GPU de la machine.

```bash
cd ai
/opt/homebrew/bin/python3.12 -m venv .venv        # ou python3.12 sous Linux/Windows
.venv/bin/pip install -r requirements.txt
```

| Script       | Rôle                                                                 | Sortie                                   |
|--------------|----------------------------------------------------------------------|------------------------------------------|
| `vision.py`  | webcam → YOLOv8n (classe personne) → alerte intrusion + buzzer        | `POST /ai/detections`, `POST /alerts`, flux MJPEG `:8001/stream` |
| `predict.py` | Isolation Forest sur fenêtres glissantes de télémétrie                | `POST /ai/predictions`, `POST /alerts` type `anomaly` |

Les deux lisent `API_PORT` et `API_KEY` dans le `.env` à la racine. Le flux vidéo s'affiche
dans le dashboard si `VITE_VIDEO_URL=http://<ip-serveur>:8001/stream` au build du dashboard.

Premier lancement de `vision.py` : téléchargement des poids `yolov8n.pt` (6 Mo) et demande
d'autorisation caméra par macOS. Les poids sont ignorés par Git.

## Choisir la webcam

`VISION_CAMERA` dans le `.env` accepte un morceau du nom (`USB`) ou un index OpenCV. Pour
vérifier quelle caméra est laquelle, `vision.py --list` enregistre une vignette par index dans
`ai/cams/`.

Ordre des index OpenCV sur macOS, constaté : **les caméras externes d'abord** (webcam USB,
iPhone en caméra de continuité), **la caméra intégrée en dernier**. Le script applique cette
règle pour retrouver la webcam par son nom. Pour la démo, désactiver quand même la caméra de
continuité sur l'iPhone (Réglages → Général → AirPlay et Continuité) : une caméra de moins,
c'est un risque de moins.

## Personnes autorisées (reconnaissance faciale)

Une personne détectée par YOLO n'est une intrusion que si son visage n'est pas reconnu dans les
3 secondes (`--grace`). Détection de visage YuNet + signature SFace, modèles OpenCV dans
`ai/models/` (téléchargés automatiquement par le script de mise en place). Les signatures sont
stockées dans `ai/faces/<nom>.npy`, **jamais commitées** : ce sont des données biométriques.

```bash
.venv/bin/python enroll.py --name leo        # 20 prises en ~10 s devant la webcam
.venv/bin/python enroll.py --list
.venv/bin/python enroll.py --delete leo
.venv/bin/python vision.py                   # charge automatiquement les personnes autorisées
.venv/bin/python vision.py --no-faces        # mode « toute personne = intrusion »
```

Sur l'image annotée : cadre vert et nom pour une personne reconnue (similarité ≥ 0,36), cadre
orange « inconnu » sinon. Une personne reconnue qui sort du champ reste « autorisée » 10 s.
