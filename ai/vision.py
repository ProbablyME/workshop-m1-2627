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
AUTH_MEMORY_S = 2.0   # une silhouette reconnue reste autorisée ce temps-là si son visage n'est plus visible


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


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
    ap.add_argument("--confirm", type=int, default=3, help="images consécutives avec un intrus avant l'alerte (3 ≈ 0,3 s)")
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

    present = False          # un intrus (personne non reconnue) est dans le champ
    auth_memory = []         # [(boîte, nom, t)] silhouettes reconnues récemment
    last_auth_post = 0.0
    intruder_frames = 0      # images consécutives avec un intrus non reconnu
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
            now = time.time()
            # --- personnes détectées par YOLO ---
            persons = []
            for b in res.boxes:
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                persons.append([float(b.conf[0]), [x1, y1, x2, y2], None])   # [confiance, boîte, nom autorisé]
            # --- visages reconnus, rattachés à la silhouette qui les contient ---
            if persons and faceid is not None:
                for face in faceid.faces(frame):
                    fx, fy, fw, fh = (int(v) for v in face[:4])
                    name, sim = faceid.identify(frame, face)
                    cx, cy = fx + fw // 2, fy + fh // 2
                    for pr in persons:
                        x1, y1, x2, y2 = pr[1]
                        if x1 <= cx <= x2 and y1 <= cy <= y2 and name:
                            pr[2] = name
                            auth_memory.append((pr[1], name, now))
                    color = (0, 200, 0) if name else (0, 165, 255)
                    cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), color, 1)
                    cv2.putText(frame, f"{name} {sim:.2f}" if name else f"inconnu {sim:.2f}", (fx, fy + fh + 14),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                # mémoire courte : une silhouette reconnue il y a < AUTH_MEMORY_S au même endroit reste autorisée
                auth_memory[:] = [m for m in auth_memory if now - m[2] < AUTH_MEMORY_S]
                for pr in persons:
                    if pr[2] is None:
                        for box, name, _ in auth_memory:
                            if iou(box, pr[1]) > 0.5:
                                pr[2] = name; break
            intruders = [pr for pr in persons if pr[2] is None]
            authorized_now = sorted({pr[2] for pr in persons if pr[2]})
            for conf, (x1, y1, x2, y2), name in persons:
                color = (0, 200, 0) if name else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                ly = y1 - 6 if y1 > 20 else y1 + 18
                cv2.putText(frame, f"{name} {conf:.0%}" if name else f"personne {conf:.0%}", (x1 + 2, ly),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            best = max(intruders, key=lambda pr: pr[0]) if intruders else None   # intrus le plus sûr
            intruder_frames = intruder_frames + 1 if best else 0
            if best and not present and intruder_frames < args.confirm:
                best = None                                                    # confirmation sur quelques images
            if api and authorized_now and now - last_auth_post > 2.0:
                last_auth_post = now
                try:
                    pr = max((pr for pr in persons if pr[2]), key=lambda pr: pr[0])
                    api.post("/ai/detections", {"source": "yolov8n+sface", "label": f"autorise:{pr[2]}", "confidence": round(pr[0], 3),
                                                "bbox": pr[1], "frame_w": 640, "frame_h": 480})
                except Exception as e:
                    print("[vision] API :", e)

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
            status = "INTRUSION" if present else (f"autorise : {', '.join(authorized_now)}" if authorized_now else "zone libre")
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
