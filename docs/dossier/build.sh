#!/usr/bin/env bash
# Génère livrables/Workshop2026-M1-G1-Dossier.pdf : dossier A4 (dossier.html) + poster A3 (poster.html).
# Rendu par Chrome en mode headless (compter 3 à 5 minutes), fusion avec pypdf (ai/.venv ou python3 avec pypdf).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/livrables"; mkdir -p "$OUT"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[[ -x "$CHROME" ]] || CHROME="$(command -v google-chrome || command -v chromium || true)"
[[ -x "$CHROME" ]] || { echo "Chrome introuvable (définir CHROME=...)" >&2; exit 1; }
TMP="$(mktemp -d)"
for f in dossier poster; do
  "$CHROME" --headless=new --disable-gpu --use-mock-keychain --password-store=basic --no-first-run \
    --user-data-dir="$TMP/profile-$f" --no-pdf-header-footer \
    --timeout=20000 --print-to-pdf="$TMP/$f.pdf" "file://$HERE/$f.html" >/dev/null 2>&1
  [[ -s "$TMP/$f.pdf" ]] || { echo "échec du rendu de $f.html" >&2; exit 1; }
done
PY="$ROOT/ai/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
"$PY" - "$TMP/dossier.pdf" "$TMP/poster.pdf" "$OUT/Workshop2026-M1-G1-Dossier.pdf" <<'PYEOF'
import sys
from pypdf import PdfReader, PdfWriter
w = PdfWriter()
for src in sys.argv[1:3]:
    for p in PdfReader(src).pages: w.add_page(p)
w.add_metadata({"/Title": "SENTINEL-X — Dossier d'ingénierie technique (Groupe 1)", "/Author": "Consortium Groupe 1 — EPSI", "/Subject": "Workshop national Bac+4 2026-27"})
with open(sys.argv[3], "wb") as f: w.write(f)
print(f"{sys.argv[3]} : {len(w.pages)} pages")
PYEOF
rm -rf "$TMP"
