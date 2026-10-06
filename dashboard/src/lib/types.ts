// Types alignés sur docs/CONTRAT_DONNEES.md et backend/app/schemas.py
export type Severity = "info" | "warning" | "critical";

export interface Telemetry {
  id: number;
  ts: string;
  device_id: string;
  uptime_ms: number | null;
  temperature: number | null;
  humidity: number | null;
  gas_raw: number | null;
  gas_ppm: number | null;
  motion: boolean;
  rssi: number | null;
  heap_free: number | null;
}

export interface Alert {
  id: number;
  ts: string;
  device_id: string;
  type: string;
  state: "on" | "off";
  value: number | null;
  severity: Severity;
  source: string;
}

export interface Device {
  id: string;
  online: boolean;
  ip: string | null;
  fw: string | null;
  last_seen: string | null;
}

export interface Command {
  id: number;
  ts: string;
  device_id: string;
  actuator: string;
  action: string;
  duration_ms: number | null;
  cmd_id: string;
  published: boolean;
}

export interface Detection {
  id: number;
  ts: string;
  source: string;
  label: string;
  confidence: number;
  bbox: number[] | null;
  frame_w: number | null;
  frame_h: number | null;
}

export interface Prediction {
  id: number;
  ts: string;
  model: string;
  score: number;
  is_anomaly: boolean;
  window_s: number | null;
  features: Record<string, number> | null;
}

export interface Health {
  status: string;
  mqtt_connected: boolean;
  db_ok: boolean;
  ws_clients: number;
  version: string;
}

export type WsMessage =
  | { kind: "telemetry"; ts: string; data: Telemetry }
  | { kind: "alert"; ts: string; data: Alert }
  | { kind: "status"; ts: string; data: Device }
  | { kind: "command"; ts: string; data: Command }
  | { kind: "detection"; ts: string; data: Detection }
  | { kind: "prediction"; ts: string; data: Prediction };
