"""Reconnaissance des personnes autorisées : YuNet (détection de visage) + SFace (signature), via OpenCV.

Les signatures enregistrées sont dans ai/faces/<nom>.npy (hors Git : données biométriques).
"""
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models"
DB = HERE / "faces"
DET = MODELS / "face_detection_yunet_2023mar.onnx"
REC = MODELS / "face_recognition_sface_2021dec.onnx"
COSINE_THRESHOLD = 0.363   # seuil recommandé par OpenCV pour SFace (similarité cosinus)


class FaceID:
    def __init__(self, width=640, height=480, conf=0.75):
        if not DET.exists() or not REC.exists():
            raise FileNotFoundError("modèles manquants dans ai/models/ (voir ai/README.md)")
        self.det = cv2.FaceDetectorYN.create(str(DET), "", (width, height), conf, 0.3, 50)
        self.rec = cv2.FaceRecognizerSF.create(str(REC), "")
        self.size = (width, height)
        self.known: dict[str, np.ndarray] = {}
        self.reload()

    def reload(self) -> int:
        self.known = {}
        DB.mkdir(exist_ok=True)
        for f in sorted(DB.glob("*.npy")):
            self.known[f.stem] = np.load(f)
        return len(self.known)

    def faces(self, frame):
        """Visages détectés : tableau (N, 15) [x, y, w, h, 5 points, score]."""
        if (frame.shape[1], frame.shape[0]) != self.size:
            self.size = (frame.shape[1], frame.shape[0]); self.det.setInputSize(self.size)
        _, res = self.det.detect(frame)
        return res if res is not None else np.empty((0, 15))

    def feature(self, frame, face):
        aligned = self.rec.alignCrop(frame, face)
        return self.rec.feature(aligned)

    def identify(self, frame, face):
        """(nom, similarité) de la personne connue la plus proche, ou (None, score) si inconnue."""
        if not self.known:
            return None, 0.0
        f = self.feature(frame, face)
        best, best_s = None, -1.0
        for name, samples in self.known.items():
            for s in samples:
                sim = float(self.rec.match(f, s.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE))
                if sim > best_s:
                    best, best_s = name, sim
        return (best if best_s >= COSINE_THRESHOLD else None), best_s

    def enroll(self, name: str, features: list) -> Path:
        arr = np.vstack([np.asarray(f).reshape(1, -1) for f in features]).astype(np.float32)
        DB.mkdir(exist_ok=True)
        out = DB / f"{name}.npy"
        np.save(out, arr)
        self.known[name] = arr
        return out
