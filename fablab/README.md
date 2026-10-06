# Fablab : fichiers pour la découpe/gravure laser et l'impression 3D

| Fichier                 | Machine            | Contenu                                                   |
|-------------------------|--------------------|-----------------------------------------------------------|
| `plaque-gravure.svg`    | Falcon A1 (laser)  | plaque 80 × 50 mm : logo AetherCorp, SENTINEL-X, S/N, sécurité |
| `boitier.py` → `export/*.step`, `*.stl` | K2 Plus (3D) | boîtier paramétrique généré par CadQuery : base, couvercle, gabarit de face ; STEP à importer dans Fusion 360 pour la finition |

Conventions du SVG : **noir** = gravure, **rouge** (trait 0,1 mm) = découpe. Dans LightBurn,
chaque couleur devient un calque avec ses propres vitesse/puissance. Convertir les textes en
chemins dans Inkscape (Chemin → Objet en chemin) si la police manque sur le poste laser.

Spécifications complètes du boîtier : [docs/BOITIER.md](../docs/BOITIER.md).

## Boîtier 3D : génération et import dans Fusion 360

```bash
cd fablab
/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install cadquery   # une fois (≈ 1,4 Go)
.venv/bin/python boitier.py                       # cotes par défaut
.venv/bin/python boitier.py --pack 118 62 --holes 108 52   # pack myDiL mesuré au pied à coulisse
```

Les cotes (parois 1,2 mm, positions des découpes, entraxe du pack, logement de la plaque) sont dans la
section PARAMÈTRES de `boitier.py`. Dans Fusion 360 : *Insérer → Insérer un fichier CAO* sur chaque
`.step` ; les corps sont modifiables (chanfreins, logos, ajustements). Imprimer d'abord
`gabarit-face.stl` (15 min) pour vérifier les découpes sur les vrais composants, puis `base.stl`
(ouverture vers le haut, sans support) et `couvercle.stl` (à plat, logement de la plaque vers le haut).
