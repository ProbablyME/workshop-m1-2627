import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "./api";
import type { Alert, Command, Detection, Device, Health, Prediction, Telemetry, WsMessage } from "./types";

const MAX_POINTS = 2000; // ≈ 2 h 45 à une télémétrie toutes les 5 s
const HISTORY_MINUTES = 120;

export type WsState = "connecting" | "open" | "closed";

export interface LiveData {
  telemetry: Telemetry[];
  alerts: Alert[];
  device: Device | null;
  detections: Detection[];
  prediction: Prediction | null;
  commands: Command[];
  health: Health | null;
  wsState: WsState;
  loadError: string | null;
  refresh: () => void;
}

export function useLiveData(): LiveData {
  const [telemetry, setTelemetry] = useState<Telemetry[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [device, setDevice] = useState<Device | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [commands, setCommands] = useState<Command[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [wsState, setWsState] = useState<WsState>("connecting");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  // Chargement initial (et à chaque refresh)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [tel, al, devs, det, pred, cmds, h] = await Promise.all([
          api.telemetry(HISTORY_MINUTES),
          api.alerts(30),
          api.devices(),
          api.detections(10),
          api.predictions(1),
          api.commands(10),
          api.health(),
        ]);
        if (cancelled) return;
        setTelemetry(tel.slice(-MAX_POINTS));
        setAlerts(al);
        setDevice(devs[0] ?? null);
        setDetections(det);
        setPrediction(pred[0] ?? null);
        setCommands(cmds);
        setHealth(h);
        setLoadError(null);
      } catch (e) {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tick]);

  // Santé de l'API toutes les 15 s
  useEffect(() => {
    const id = setInterval(() => {
      api.health().then(setHealth).catch(() => setHealth(null));
    }, 15_000);
    return () => clearInterval(id);
  }, []);

  // WebSocket avec reconnexion exponentielle
  const retryRef = useRef(1000);
  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      setWsState("connecting");
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        retryRef.current = 1000;
        setWsState("open");
      };
      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(ev.data as string) as WsMessage;
        } catch {
          return;
        }
        switch (msg.kind) {
          case "telemetry":
            setTelemetry((prev) => [...prev, msg.data].slice(-MAX_POINTS));
            break;
          case "alert":
            setAlerts((prev) => [msg.data, ...prev].slice(0, 50));
            break;
          case "status":
            setDevice(msg.data);
            break;
          case "command":
            setCommands((prev) => [msg.data, ...prev].slice(0, 20));
            break;
          case "detection":
            setDetections((prev) => [msg.data, ...prev].slice(0, 20));
            break;
          case "prediction":
            setPrediction(msg.data);
            break;
        }
      };
      ws.onclose = () => {
        setWsState("closed");
        if (stopped) return;
        timer = window.setTimeout(connect, retryRef.current);
        retryRef.current = Math.min(retryRef.current * 2, 10_000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { telemetry, alerts, device, detections, prediction, commands, health, wsState, loadError, refresh };
}
