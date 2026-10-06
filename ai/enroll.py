#!/usr/bin/env python3
"""Enregistre le visage d'une personne autorisée depuis la webcam.

    ai/.venv/bin/python ai/enroll.py --name leo              # 20 prises en ~10 s, bouger légèrement la tête
    ai/.venv/bin/python ai/enroll.py --name leo --camera 0   # autre caméra
    ai/.venv/bin/python ai/enroll.py --list                  # personnes enregistrées
    ai/.venv/bin/python ai/enroll.py --delete leo
"""
import argparse
import time

import cv2

from common import load_env
from faces import DB, FaceID
from vision import resolve_camera


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="identifiant de la personne (lettres, chiffres, tirets)")
    ap.add_argument("--camera", default=None)
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--delete", metavar="NOM")
    a = ap.parse_args()
    if a.list:
        names = [f.stem for f in sorted(DB.glob("*.npy"))]
        print("personnes autorisées :", ", ".join(names) if names else "aucune"); return
    if a.delete:
        p = DB / f"{a.delete}.npy"
        print("supprimé" if p.exists() and not p.unlink() else "inconnu"); return
    if not a.name:
        ap.error("--name requis")
    env = load_env()
    cam = resolve_camera(a.camera if a.camera is not None else env.get("VISION_CAMERA", "USB"))
    fid = FaceID()
    cap = cv2.VideoCapture(cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("webcam introuvable")
    print(f"[enroll] {a.name} : regarde la caméra, tourne légèrement la tête ; {a.samples} prises…")
    feats = []; last = 0.0; t0 = time.time()
    while len(feats) < a.samples and time.time() - t0 < 60:
        ok, frame = cap.read()
        if not ok: continue
        frame = cv2.resize(frame, (640, 480))
        faces = fid.faces(frame)
        if len(faces) == 1 and time.time() - last > 0.4:
            feats.append(fid.feature(frame, faces[0])); last = time.time()
            print(f"  prise {len(feats)}/{a.samples}")
        elif len(faces) > 1:
            print("  plusieurs visages : une seule personne devant la caméra")
    cap.release()
    if len(feats) < 5:
        raise SystemExit("trop peu de prises : visage pas détecté (lumière, distance 50 cm à 1 m)")
    out = fid.enroll(a.name, feats)
    print(f"[enroll] {len(feats)} signatures enregistrées dans {out}")


if __name__ == "__main__":
    main()
