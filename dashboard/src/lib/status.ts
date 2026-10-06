import type { Severity } from "./types";

export type Status = "good" | "warning" | "serious" | "critical" | "neutral";

// Seuils du contrat §6 (identiques au firmware)
export const THRESHOLDS = {
  temp: { warn: 35, crit: 45 },
  hum: { warn: 80, crit: 90 },
  gas: { deltaWarn: 80, deltaCrit: 200 }, // relatifs à la ligne de base (firmware)
} as const;

export const STATUS_LABEL: Record<Status, string> = {
  good: "Nominal",
  warning: "Attention",
  serious: "Élevé",
  critical: "Critique",
  neutral: "Inconnu",
};

// Icône + libellé : la couleur ne porte jamais seule l'information
export const STATUS_ICON: Record<Status, string> = {
  good: "✓",
  warning: "▲",
  serious: "◆",
  critical: "✕",
  neutral: "·",
};

function band(v: number | null, warn: number, crit: number): Status {
  if (v === null || Number.isNaN(v)) return "neutral";
  if (v > crit) return "critical";
  if (v > warn) return "warning";
  return "good";
}

export const tempStatus = (v: number | null) => band(v, THRESHOLDS.temp.warn, THRESHOLDS.temp.crit);
export const humStatus = (v: number | null) => band(v, THRESHOLDS.hum.warn, THRESHOLDS.hum.crit);
// Gaz : seuils relatifs à une ligne de base connue du boîtier seul → on suit sa dernière alerte gaz
export function gasAlertStatus(alerts: Array<{ type: string; state: string; severity: Severity }>): Status {
  const last = alerts.find((a) => a.type === "gas");
  if (!last || last.state === "off") return "good";
  return severityStatus(last.severity);
}
export const motionStatus = (m: boolean | null): Status => (m === null ? "neutral" : m ? "serious" : "good");

export function severityStatus(s: Severity): Status {
  return s === "critical" ? "critical" : s === "warning" ? "warning" : "good";
}

export const ALERT_TYPE_LABEL: Record<string, string> = {
  motion: "Présence",
  gas: "Gaz / fumée",
  temperature: "Température",
  humidity: "Humidité",
  sensor_fault: "Capteur en défaut",
  intrusion: "Intrusion (IA)",
  anomaly: "Anomalie prédictive",
};

export const ACTUATOR_LABEL: Record<string, string> = {
  buzzer: "Buzzer",
  led_red: "LED rouge",
  led_green: "LED verte",
  led: "LED (toutes)",
  camera: "Intrusion caméra (IA)",
};

export function fmtTime(ts: string | number, withSeconds = true): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    ...(withSeconds ? { second: "2-digit" } : {}),
  });
}

export function fmtAgo(ts: string | null): string {
  if (!ts) return "jamais";
  const s = Math.max(0, Math.round((Date.now() - new Date(ts).getTime()) / 1000));
  if (s < 60) return `il y a ${s} s`;
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  return `il y a ${Math.round(s / 3600)} h`;
}
