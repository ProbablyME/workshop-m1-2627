import type { Alert, Command, Detection, Device, Health, Prediction, Telemetry } from "./types";

// Même origine : en dev Vite proxifie /api et /ws, en prod nginx. La clé API est injectée
// par le proxy, jamais présente dans le navigateur.
const BASE = "/api/v1";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return (await r.json()) as T;
}

export interface CommandBody {
  actuator: "buzzer" | "led_red" | "led_green" | "led" | "camera";
  action: "on" | "off" | "blink" | "pulse";
  duration_ms?: number;
}

export const api = {
  health: () => get<Health>("/health"),
  telemetry: (minutes: number) => get<Telemetry[]>(`/telemetry?minutes=${minutes}&limit=5000`),
  alerts: (limit = 30) => get<Alert[]>(`/alerts?limit=${limit}`),
  devices: () => get<Device[]>("/devices"),
  detections: (limit = 10) => get<Detection[]>(`/ai/detections?limit=${limit}`),
  predictions: (limit = 1) => get<Prediction[]>(`/ai/predictions?limit=${limit}`),
  commands: (limit = 10) => get<Command[]>(`/commands?limit=${limit}`),
  async sendCommand(body: CommandBody): Promise<Command> {
    const r = await fetch(BASE + "/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST /commands → ${r.status}`);
    return (await r.json()) as Command;
  },
};

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws`;
}
