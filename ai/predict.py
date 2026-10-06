#!/usr/bin/env python3
"""Maintenance prédictive Sentinel-X : Isolation Forest sur les séries de télémétrie.

    ai/.venv/bin/python ai/predict.py                # boucle : score toutes les 30 s
    ai/.venv/bin/python ai/predict.py --once         # un seul score, affiché
    ai/.venv/bin/python ai/predict.py --train-hours 6 --window 300

Principe (sujet : pas de simple "if temp > 40") : on découpe l'historique en fenêtres glissantes
et on calcule pour chacune des caractéristiques cinétiques — pente de température, pente de gaz,
variabilité, corrélation temp/gaz. Un Isolation Forest apprend la "forme normale" de ces fenêtres
et signale celles qui s'en écartent, par exemple une hausse lente et simultanée de la température
et du gaz, bien avant les seuils d'alerte du boîtier.
"""
import argparse
import time
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest

from common import Api, load_env

FEATURES = ["temp_mean", "temp_slope", "gas_mean", "gas_slope", "gas_std", "hum_slope", "temp_gas_corr"]


def parse_ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def windows(rows: list[dict], window_s: int, step_s: int):
    """Découpe les mesures (triées) en fenêtres glissantes ; renvoie (t_fin, features)."""
    pts = [(parse_ts(r["ts"]), r["temperature"], r["gas_raw"], r["humidity"]) for r in rows
           if r["temperature"] is not None and r["gas_raw"] is not None and r["humidity"] is not None]
    if len(pts) < 10:
        return []
    out = []
    t_start, t_end = pts[0][0], pts[-1][0]
    t = t_start + window_s
    while t <= t_end:
        w = [p for p in pts if t - window_s <= p[0] <= t]
        if len(w) >= 6:
            out.append((t, features(w)))
        t += step_s
    return out


def slope(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 2 or x.std() == 0:
        return 0.0
    return float(np.polyfit((x - x.mean()) / 60.0, y, 1)[0])   # unité par minute


def features(w):
    t = [p[0] for p in w]; temp = [p[1] for p in w]; gas = [p[2] for p in w]; hum = [p[3] for p in w]
    corr = float(np.corrcoef(temp, gas)[0, 1]) if np.std(temp) > 0 and np.std(gas) > 0 else 0.0
    return [float(np.mean(temp)), slope(t, temp), float(np.mean(gas)), slope(t, gas),
            float(np.std(gas)), slope(t, hum), corr]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-hours", type=int, default=12, help="historique utilisé pour apprendre la normale")
    ap.add_argument("--window", type=int, default=300, help="fenêtre d'analyse en secondes")
    ap.add_argument("--step", type=int, default=60, help="pas entre deux fenêtres (s)")
    ap.add_argument("--contamination", type=float, default=0.03)
    ap.add_argument("--interval", type=int, default=30, help="secondes entre deux scores")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    api = Api(load_env())
    model = None
    last_train = 0.0
    anomaly = False

    while True:
        now = time.time()
        if model is None or now - last_train > 1800:   # ré-apprentissage toutes les 30 min
            rows = api.get("/telemetry", minutes=args.train_hours * 60, limit=10000)
            ws = windows(rows, args.window, args.step)
            if len(ws) < 20:
                print(f"[predict] pas assez d'historique ({len(ws)} fenêtres, 20 minimum) : attente…")
                if args.once:
                    return
                time.sleep(args.interval); continue
            X = np.array([f for _, f in ws])
            model = IsolationForest(n_estimators=200, contamination=args.contamination, random_state=42).fit(X)
            last_train = now
            print(f"[predict] modèle entraîné sur {len(ws)} fenêtres de {args.window}s ({len(rows)} mesures, {args.train_hours} h)")

        recent = api.get("/telemetry", minutes=max(2, args.window // 60 + 1), limit=2000)
        ws = windows(recent, args.window, args.window)
        if not ws:
            print("[predict] pas de fenêtre récente complète")
        else:
            f = ws[-1][1]
            score = float(model.decision_function([f])[0])      # < 0 = anormal
            is_anom = bool(model.predict([f])[0] == -1)
            feats = dict(zip(FEATURES, [round(v, 3) for v in f]))
            print(f"[predict] score {score:+.3f} {'ANOMALIE' if is_anom else 'normal'}  "
                  f"temp {feats['temp_mean']:.1f}°C ({feats['temp_slope']:+.2f}/min)  gaz {feats['gas_mean']:.0f} ({feats['gas_slope']:+.1f}/min)")
            try:
                api.post("/ai/predictions", {"model": "isolation_forest", "score": round(score, 4), "is_anomaly": is_anom,
                                             "window_s": args.window, "features": feats})
                if is_anom and not anomaly:
                    api.post("/alerts", {"type": "anomaly", "state": "on", "value": round(score, 3), "severity": "warning"})
                elif not is_anom and anomaly:
                    api.post("/alerts", {"type": "anomaly", "state": "off", "value": round(score, 3), "severity": "info"})
                anomaly = is_anom
            except Exception as e:
                print("[predict] API :", e)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
