# Fablab : fichiers pour la découpe/gravure laser et l'impression 3D

| Fichier                 | Machine            | Contenu                                                   |
|-------------------------|--------------------|-----------------------------------------------------------|
| `plaque-gravure.svg`    | Falcon A1 (laser)  | plaque 80 × 50 mm : logo AetherCorp, SENTINEL-X, S/N, sécurité |
| `*.f3d` / `*.3mf`       | K2 Plus (3D)       | à exporter depuis Fusion360 (base, face avant, couvercle) |

Conventions du SVG : **noir** = gravure, **rouge** (trait 0,1 mm) = découpe. Dans LightBurn,
chaque couleur devient un calque avec ses propres vitesse/puissance. Convertir les textes en
chemins dans Inkscape (Chemin → Objet en chemin) si la police manque sur le poste laser.

Spécifications complètes du boîtier : [docs/BOITIER.md](../docs/BOITIER.md).
