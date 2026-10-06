#!/usr/bin/env python3
"""Vision Sentinel-X : webcam → YOLOv8n → détection de personne → API + flux vidéo pour le dashboard.

    ai/.venv/bin/python ai/vision.py                 # webcam 0, flux MJPEG sur http://localhost:8001/stream
    ai/.venv/bin/python ai/vision.py --camera 1 --show --no-buzzer

Chaque trame est réduite en 640x480 avant l'inférence (sujet : < 100 ms par trame).
Quand une personne apparaît : POST /ai/detections (toutes les 2 s tant qu'elle est là),
POST /alerts type=intrusion state=on, et commande buzzer. Quand elle disparaît 5 s : state=off.
"""
import argparse
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
from ultralytics import YOLO

from common import Api, load_env
from faces import FaceID

PERSON = 0  # classe COCO "person"


class Stream:
    """Dernière trame annotée, servie en MJPEG (multipart/x-mixed-replace)."""
    jpeg = b""
    lock = threading.Lock()


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silencieux
        pass

    def do_GET(self):
        if self.path != "/stream":
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                with Stream.lock:
                    buf = Stream.jpeg
                if buf:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(buf))
                    self.wfile.write(buf + b"\r\n")
                time.sleep(0.08)
        except (BrokenPipeError, ConnectionResetError):
            pass


def camera_names() -> list[str]:
    """Noms des caméras dans l'ordre des index OpenCV (macOS : même énumération AVFoundation)."""
    try:
        import AVFoundation as AV  # pyobjc, macOS seulement
        def query(dev_type):
            sess = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
                [dev_type], AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified)
            return [str(d.localizedName()) for d in sess.devices()]
        # Ordre constaté d'OpenCV (AVFoundation) : caméras externes d'abord, intégrée en dernier
        return query(AV.AVCaptureDeviceTypeExternal) + query(AV.AVCaptureDeviceTypeBuiltInWideAngleCamera)
    except Exception:
        return []


def resolve_camera(spec: str) -> int:
    """'1' → 1 ; 'USB' → index de la première caméra dont le nom contient 'usb' (sinon 0)."""
    spec = (spec or "0").strip()
    if spec.lstrip("-").isdigit():
        return int(spec)
    names = camera_names()
    for i, n in enumerate(names):
        if spec.lower() in n.lower():
            print(f"[vision] caméra {i} : {n}")
            return i
    print(f"[vision] aucune caméra nommée '{spec}' parmi {names or 'inconnues'} → index 0")
    return 0


def probe_cameras(max_index: int = 5) -> list[tuple[int, str, str]]:
    """(index, nom, résolution) pour chaque caméra qu'OpenCV arrive à ouvrir."""
    names = camera_names()
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            cap.release(); continue
        ok, _ = cap.read()
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if ok:
            found.append((i, names[i] if i < len(names) else f"caméra {i}", f"{w}x{h}"))
    return found


def choose_camera(default_spec: str) -> int:
    """Affiche les caméras détectées et demande laquelle utiliser (Entrée = choix par défaut)."""
    cams = probe_cameras()
    if not cams:
        raise SystemExit("aucune caméra détectée (autoriser l'accès caméra dans Réglages Système)")
    default = cams[0][0]
    if default_spec.strip().lstrip("-").isdigit():
        if int(default_spec) in [c[0] for c in cams]: default = int(default_spec)
    else:
        for i, n, _ in cams:
            if default_spec.lower() in n.lower(): default = i; break
    print("\nCaméras détectées :")
    for i, n, res in cams:
        print(f"  [{i}] {n:<28} {res}{'   (défaut)' if i == default else ''}")
    while True:
        try:
            raw = input(f"Caméra à utiliser [{default}] : ").strip()
        except EOFError:
            return default
        if raw == "":
            return default
        if raw.isdigit() and int(raw) in [c[0] for c in cams]:
            return int(raw)
        print("  → entrer un des numéros entre crochets")


def list_cameras() -> None:
    """Ouvre les index 0 à 4, enregistre une vignette de chacun dans ai/cams/ pour les identifier."""
    import os
    os.makedirs("cams", exist_ok=True)
    names = camera_names()
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            continue
        t0 = time.time(); frame = None
        while time.time() - t0 < 1.5:          # laisse l'exposition se régler
            ok, f = cap.read()
            if ok: frame = f
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if frame is not None:
            cv2.imwrite(f"cams/cam-{i}.jpg", cv2.resize(frame, (480, 270)))
            name = names[i] if i < len(names) else "?"
            print(f"index {i} : {name}  {w}x{h} → cams/cam-{i}.jpg")
    print("Dans .env : VISION_CAMERA=USB (morceau du nom) ou VISION_CAMERA=<index>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default=None, help="index ou morceau du nom de la webcam ; sans cette option, le script liste les caméras et demande laquelle utiliser")
    ap.add_argument("--list", action="store_true", help="liste les caméras disponibles avec une vignette dans ai/cams/")
    ap.add_argument("--model", default="yolov8n.pt", help="poids YOLO (téléchargés au premier lancement)")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--port", type=int, default=8001, help="port du flux MJPEG")
    ap.add_argument("--show", action="store_true", help="fenêtre OpenCV locale")
    ap.add_argument("--no-buzzer", action="store_true", help="ne pas déclencher le buzzer sur intrusion")
    ap.add_argument("--no-api", action="store_true", help="test caméra seule, sans serveur")
    ap.add_argument("--no-faces", action="store_true", help="désactiver la reconnaissance des personnes autorisées")
    ap.add_argument("--grace", type=float, default=3.0, help="secondes laissées à une personne pour être reconnue avant l'alerte")
    args = ap.parse_args()

    env = load_env()
    if args.list:
        list_cameras(); return
    if args.camera is not None:
        args.camera = resolve_camera(args.camera)                       # --camera : pas de question
    elif sys.stdin.isatty():
        args.camera = choose_camera(env.get("VISION_CAMERA", "USB"))    # terminal : liste + choix
    else:
        args.camera = resolve_camera(env.get("VISION_CAMERA", "USB"))   # lancé sans terminal : automatique
    api = None if args.no_api else Api(env)
    model = YOLO(args.model)
    faceid = None
    if not args.no_faces:
        try:
            faceid = FaceID()
            print(f"[vision] personnes autorisées : {', '.join(faceid.known) or 'aucune (ai/enroll.py --name ...)'}")
        except FileNotFoundError as e:
            print("[vision] reconnaissance désactivée :", e)
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit(f"webcam {args.camera} introuvable (autoriser l'accès caméra dans Réglages Système)")

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), StreamHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[vision] flux MJPEG : http://localhost:{args.port}/stream  (Ctrl+C pour arrêter)")

    present = False          # une personne est dans le champ
    unknown_since = None     # depuis quand une personne non reconnue est dans le champ
    authorized = None        # nom de la personne autorisée reconnue (ou None)
    last_known_at = 0.0
    last_seen = 0.0
    last_post = 0.0
    fps_t, fps_n, fps = time.time(), 0, 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1); continue
            frame = cv2.resize(frame, (640, 480))
            t0 = time.time()
            res = model.predict(frame, imgsz=640, conf=args.conf, classes=[PERSON], verbose=False)[0]
            infer_ms = (time.time() - t0) * 1000
            boxes = res.boxes
            now = time.time()
            best = None
            for b in boxes:
                c = float(b.conf[0])
                if best is None or c > best[0]:
                    x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                    best = (c, [x1, y1, x2, y2])
                cv2.rectangle(frame, (int(b.xyxy[0][0]), int(b.xyxy[0][1])), (int(b.xyxy[0][2]), int(b.xyxy[0][3])), (0, 0, 255), 2)
                x1, y1 = int(b.xyxy[0][0]), int(b.xyxy[0][1])
                ly = y1 - 6 if y1 > 20 else y1 + 18          # étiquette sous le bord si le cadre touche le haut
                cv2.putText(frame, f"personne {c:.0%}", (x1 + 2, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

            # --- reconnaissance des personnes autorisées ---
            if best and faceid is not None:
                for face in faceid.faces(frame):
                    x, y, w, h = (int(v) for v in face[:4])
                    name, sim = faceid.identify(frame, face)
                    if name:
                        authorized, last_known_at = name, now
                    color = (0, 200, 0) if name else (0, 165, 255)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
                    cv2.putText(frame, f"{name} {sim:.2f}" if name else f"inconnu {sim:.2f}", (x, y + h + 14),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if authorized and now - last_known_at > 10.0:   # plus vu depuis 10 s : on oublie l'autorisation
                authorized = None

            if best and authorized:                        # personne autorisée : pas d'intrusion
                last_seen = now
                unknown_since = None
                if present:
                    present = False
                    print(f"[vision] {authorized} reconnu : fin d'alerte")
                    if api:
                        try:
                            api.post("/alerts", {"type": "intrusion", "state": "off", "value": 0, "severity": "info"})
                            api.post("/commands", {"actuator": "camera", "action": "off"})
                        except Exception as e:
                            print("[vision] API :", e)
                if api and now - last_post > 2.0:
                    last_post = now
                    try:
                        api.post("/ai/detections", {"source": "yolov8n+sface", "label": f"autorise:{authorized}", "confidence": round(best[0], 3),
                                                    "bbox": best[1], "frame_w": 640, "frame_h": 480})
                    except Exception as e:
                        print("[vision] API :", e)
                best_for_alert = None
            else:
                best_for_alert = best
                if best and faceid is not None and unknown_since is None:
                    unknown_since = now                    # délai de grâce avant l'alerte
            best = best_for_alert
            if best and faceid is not None and not present and now - unknown_since < args.grace:
                best = None                                # on attend encore une reconnaissance
            if not best_for_alert:
                unknown_since = None

            if best:
                last_seen = now
                if not present:
                    present = True
                    print(f"[vision] INTRUSION détectée ({best[0]:.0%}) : personne non reconnue")
                    if api:
                        try:
                            api.post("/alerts", {"type": "intrusion", "state": "on", "value": round(best[0], 2), "severity": "critical"})
                            api.post("/commands", {"actuator": "camera", "action": "on"})   # écran "ALERTE CAMERA", LED rouge, bip
                            if args.no_buzzer:
                                api.post("/commands", {"actuator": "buzzer", "action": "off"})
                        except Exception as e:
                            print("[vision] API :", e)
                if api and now - last_post > 2.0:
                    last_post = now
                    try:
                        api.post("/ai/detections", {"source": "yolov8n", "label": "person", "confidence": round(best[0], 3),
                                                    "bbox": best[1], "frame_w": 640, "frame_h": 480})
                    except Exception as e:
                        print("[vision] API :", e)
            elif present and now - last_seen > 5.0:
                present = False
                print("[vision] zone libre")
                if api:
                    try:
                        api.post("/alerts", {"type": "intrusion", "state": "off", "value": 0, "severity": "info"})
                        api.post("/commands", {"actuator": "camera", "action": "off"})   # retour à la normale sur le boîtier
                    except Exception as e:
                        print("[vision] API :", e)

            fps_n += 1
            if now - fps_t >= 1.0:
                fps, fps_n, fps_t = fps_n / (now - fps_t), 0, now
            status = "INTRUSION" if present else (f"autorise : {authorized}" if authorized else "zone libre")
            cv2.putText(frame, f"SENTINEL-X IA  {status}  {infer_ms:.0f} ms  {fps:.1f} fps", (8, 468),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255) if present else (0, 200, 0), 2)
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with Stream.lock:
                    Stream.jpeg = jpg.tobytes()
            if args.show:
                cv2.imshow("SENTINEL-X vision", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        srv.shutdown()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
