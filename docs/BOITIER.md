# Boîtier SENTINEL-X : spécifications pour la CAO (Fusion360) et le Fablab

Consignes du sujet : modélisation sur **Fusion360 exclusivement**, impression sur Creality K2 Plus,
cloisons **1,2 mm maximum**, électronique encapsulée proprement, **écran OLED visible**,
passe-câbles propres **sans fil apparent**, plaque gravée au laser (logo AetherCorp, consignes
de sécurité, numéro de série). L'impression 3D est longue : lancer la base dès lundi soir.

## 1. Ce qu'il y a à loger (mesurer au pied à coulisse lundi, valeurs indicatives)

| Élément                               | Encombrement (L × l × h)       | Contrainte de montage                                   |
|---------------------------------------|--------------------------------|---------------------------------------------------------|
| Pack myDiL (ESP + 2 breadboards)      | **à mesurer**, ≈ 115 × 60 × 22 mm | 4 oreilles de fixation : relever l'entraxe des trous, ne pas désassembler |
| OLED 0.96" I2C                        | PCB 27 × 27 mm, 4 trous Ø2 (entraxe ≈ 23,5 mm) | zone d'affichage 22 × 11 mm décalée vers le haut du PCB |
| PIR HC-SR501                          | PCB 32 × 24 mm, dôme Ø 23 mm, h ≈ 25 mm | trou Ø 23,5 mm en face avant, dôme en saillie, potentiomètres accessibles |
| MQ-2 (module)                         | PCB 32 × 20 mm, capsule Ø 16 mm, h ≈ 22 mm | grille d'aération obligatoire, chauffe (≈ 50 °C)     |
| DHT22 (module)                        | 38 × 20 × 8 mm                 | fentes d'aération, loin du MQ-2 pour ne pas fausser la température |
| Buzzer actif                          | Ø 12 mm, h 9 mm                | grille de 5 à 7 trous Ø 2 mm devant                      |
| LED bicolore 5 mm                     | Ø 5 mm                         | trou Ø 5,2 mm, collée ou support LED                     |
| Convertisseur DC-DC                   | ≈ 43 × 21 × 12 mm              | production uniquement                                    |
| 2 Wago + arrivée 7,5 V                | ≈ 20 × 13 × 8 mm chacun        | passe-câble Ø 6 mm ou presse-étoupe                      |
| Micro-USB de l'ESP                    | ouverture 12 × 8 mm            | alignée sur le port, accessible sans ouvrir le boîtier    |

## 2. Architecture proposée : 3 pièces

Modèle généré par `fablab/boitier.py` (CadQuery → STEP/STL, voir `fablab/README.md`), à importer et finaliser dans Fusion 360.

1. **Base** (le plus long à imprimer, à lancer en premier) : bac avec 4 plots à vis pour le pack
   myDiL, logements DC-DC et Wago, ouverture micro-USB latérale, passe-câble d'alimentation,
   pieds et chanfreins 45° pour imprimer sans support.
2. **Face avant** (pièce fine, rapide) : fenêtre OLED avec 4 plots, trou PIR, trou LED, grille
   buzzer, grille MQ-2, fentes DHT22, et l'emplacement en retrait pour la plaque gravée.
3. **Couvercle** : fermeture par 4 vis M3 (inserts chauffants ou trous Ø 2,8 mm pour vis
   autotaraudeuses), aérations latérales.

Dimensions intérieures cibles : ≈ 140 × 95 × 55 mm. À ajuster après mesure du pack.

## 3. Paramètres Fusion360 (User Parameters, pour tout ajuster en 30 secondes)

| Paramètre      | Valeur | Commentaire                                   |
|----------------|--------|-----------------------------------------------|
| `wall`         | 1,2 mm | consigne myDiL, = 3 lignes de buse 0,4 mm     |
| `clear`        | 0,3 mm | jeu entre pièces imprimées                    |
| `inner_L`      | 140 mm | longueur intérieure                           |
| `inner_W`      | 95 mm  | largeur intérieure                            |
| `inner_H`      | 55 mm  | hauteur intérieure                            |
| `screw`        | 2,8 mm | trou vis M3 autotaraudeuse                    |
| `pir_hole`     | 23,5 mm| dôme PIR                                      |
| `led_hole`     | 5,2 mm | LED 5 mm                                      |
| `oled_win_W`   | 24 mm  | fenêtre écran (zone active 22 mm + jeu)       |
| `oled_win_H`   | 13 mm  |                                               |
| `plate_L`      | 80 mm  | plaque gravée laser                           |
| `plate_W`      | 50 mm  |                                               |
| `plate_T`      | 3 mm   | plexi ou bois 3 mm                            |

## 4. Réglages d'impression (Creality Print / K2 Plus)

- Matière PLA, buse 0,4 mm, couches 0,2 mm, parois 3 lignes (1,2 mm), remplissage 15 % gyroïde.
- Pas de support : toutes les ouvertures latérales en forme de « pont » ≤ 10 mm ou avec chanfrein 45° en haut.
- Orienter la face avant à plat, fenêtre vers le haut. Base ouverture vers le haut.
- Temps estimé : base ≈ 4 à 5 h, face avant ≈ 1 h, couvercle ≈ 2 h. Lancer la base lundi soir.
- Première impression : un **gabarit de test** 2 mm d'épaisseur avec juste les découpes (OLED, PIR, LED) pour vérifier les cotes en 15 minutes avant d'imprimer la vraie face.

## 5. Gravure et découpe laser (Falcon A1)

- Support : plexi 3 mm (rendu « produit fini ») ou contreplaqué 3 mm (plus rapide).
- Fichier : `fablab/plaque-gravure.svg`, 80 × 50 mm. Noir = gravure, rouge = découpe.
- Contenu : logo AetherCorp, « SENTINEL-X · Edge Node », S/N `SX-G1-01`, pictogrammes de sécurité
  (tension 7,5 V, ne pas ouvrir sous tension, surface chaude côté MQ-2), « Groupe 1 · EPSI 2026 ».
- Dans LightBurn ou Falcon Design Space : importer le SVG, assigner gravure au calque noir
  (vitesse haute, puissance basse) et découpe au calque rouge (vitesse basse, 2 passes sur plexi).
- Fixation : 4 trous Ø 3,2 mm aux coins (vis M3) ou double-face, dans le retrait prévu en face avant.
- Bonus rapide : une seconde petite plaque 40 × 15 mm « AetherCorp » à coller sur le couvercle.

## 6. Checklist Fablab (à cocher)

- [ ] Lundi : mesures du pack, des modules et de l'entraxe des trous. Esquisse Fusion360 avec les paramètres ci-dessus.
- [ ] Lundi soir : impression du gabarit de test puis de la base.
- [ ] Mardi : face avant et couvercle. Export SVG final de la plaque, test de gravure sur chute.
- [ ] Mercredi : montage électronique dans le boîtier, gestion des câbles (colliers, chemins de câbles imprimés), tournage B-Roll.
- [ ] Jeudi matin (gel du code) : finitions, plaque collée, étiquette S/N sous le boîtier, photos pour le dossier.
