#!/usr/bin/env python3
"""Simule le boîtier Sentinel-X sans matériel : publie télémétrie + alertes en MQTT.

Usage (depuis la racine du dépôt, avec le .env rempli) :
    python backend/tools/simulate_esp.py            # port 1883 (clair)
    python backend/tools/simulate_esp.py --tls      # port 8883 avec infra/mosquitto/certs/ca.crt
    python backend/tools/simulate_esp.py --period 2 --intrusion
"""
import argparse
import json
import math
import os
import random
import signal
import ssl
import time
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith(("MQTT_", "POSTGRES_"))})
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--tls", action="store_true", help="utilise MQTTS 8883 + CA locale")
    ap.add_argument("--period", type=float, default=5.0, help="secondes entre deux télémétries")
    ap.add_argument("--intrusion", action="store_true", help="déclenche des alertes PIR aléatoires")
    ap.add_argument("--drift", action="store_true", help="dérive lente temp + gaz (scénario IA prédictive)")
    args = ap.parse_args()

    # SIGTERM (docker stop, kill) → même sortie propre que Ctrl+C : statut offline publié
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    env = load_env()
    prefix = env.get("MQTT_TOPIC_PREFIX", "sentinel/g1")
    device = "SX-G1-01"

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sx-sim")
    if env.get("MQTT_USER"):
        c.username_pw_set(env["MQTT_USER"], env.get("MQTT_PASSWORD", ""))
    port = 1883
    if args.tls:
        port = 8883
        c.tls_set(ca_certs=str(ROOT / "infra/mosquitto/certs/ca.crt"), tls_version=ssl.PROTOCOL_TLS_CLIENT)
        c.tls_insecure_set(True)  # IP locale sans DNS : on fait confiance à la CA, pas au nom
    c.will_set(f"{prefix}/status", json.dumps({"device_id": device, "online": False}), qos=1, retain=True)
    c.connect(args.host, port, keepalive=30)
    c.loop_start()
    c.publish(f"{prefix}/status", json.dumps({"device_id": device, "online": True, "ip": "127.0.0.1", "fw": "sim"}),
              qos=1, retain=True)
    print(f"[sim] connecté à {args.host}:{port}, topics {prefix}/*  (Ctrl+C pour arrêter)")

    t0 = time.time()
    motion = False
    gas_alarm = False
    try:
        while True:
            t = time.time() - t0
            drift = (t / 60.0) if args.drift else 0.0
            temp = 23.0 + 1.5 * math.sin(t / 40) + random.gauss(0, 0.15) + 0.8 * drift
            hum = 45.0 + 4 * math.cos(t / 70) + random.gauss(0, 0.4)
            gas = int(300 + 15 * math.sin(t / 25) + random.gauss(0, 6) + 40 * drift)

            if args.intrusion and random.random() < 0.08:
                motion = not motion
                c.publish(f"{prefix}/alerts", json.dumps({
                    "device_id": device, "uptime_ms": int(t * 1000), "type": "motion",
                    "state": "on" if motion else "off", "value": int(motion), "severity": "warning"}), qos=1)
                print(f"[sim] ALERTE motion {'ON' if motion else 'OFF'}")

            if (gas > 400) != gas_alarm:
                gas_alarm = gas > 400
                c.publish(f"{prefix}/alerts", json.dumps({
                    "device_id": device, "uptime_ms": int(t * 1000), "type": "gas",
                    "state": "on" if gas_alarm else "off", "value": gas,
                    "severity": "critical" if gas > 600 else "warning"}), qos=1)
                print(f"[sim] ALERTE gaz {'ON' if gas_alarm else 'OFF'} ({gas})")

            payload = {
                "device_id": device, "uptime_ms": int(t * 1000),
                "temperature": round(temp, 1), "humidity": round(hum, 1),
                "gas_raw": max(0, min(1023, gas)), "gas_ppm": round(max(0, gas - 250) * 0.9, 1),
                "motion": motion, "rssi": random.randint(-70, -50), "heap_free": random.randint(28000, 34000),
            }
            c.publish(f"{prefix}/telemetry", json.dumps(payload), qos=0)
            print(f"[sim] {payload['temperature']}°C {payload['humidity']}% gaz={payload['gas_raw']} motion={motion}")
            time.sleep(args.period)
    except KeyboardInterrupt:
        pass
    finally:
        c.publish(f"{prefix}/status", json.dumps({"device_id": device, "online": False}), qos=1, retain=True)
        time.sleep(0.3)
        c.loop_stop()
        c.disconnect()


if __name__ == "__main__":
    main()
