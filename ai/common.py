"""Accès à l'API Sentinel-X pour les scripts IA (lecture du .env à la racine du dépôt)."""
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith(("API_", "VISION_", "PREDICT_"))})
    return env


class Api:
    def __init__(self, env: dict):
        port = env.get("API_PORT", "8000")
        self.base = env.get("API_URL", f"http://localhost:{port}") + "/api/v1"
        self.headers = {"X-API-Key": env.get("API_KEY", ""), "Content-Type": "application/json"}
        self.s = requests.Session()

    def get(self, path: str, **params):
        r = self.s.get(self.base + path, params=params, timeout=5)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict):
        r = self.s.post(self.base + path, json=body, headers=self.headers, timeout=5)
        r.raise_for_status()
        return r.json()
