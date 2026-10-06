import type { Alert } from "../lib/types";
import { ALERT_TYPE_LABEL, fmtTime, severityStatus } from "../lib/status";
import { StatusBadge } from "./StatusBadge";

function fmtValue(a: Alert): string {
  if (a.value === null) return "";
  switch (a.type) {
    case "temperature":
      return `${a.value.toFixed(1)} °C`;
    case "humidity":
      return `${a.value.toFixed(0)} %`;
    case "gas":
      return `${Math.round(a.value)} raw`;
    default:
      return "";
  }
}

const SOURCE_LABEL: Record<string, string> = { esp: "boîtier", api: "API", ai: "IA" };

export function AlertsFeed({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="card">
      <h2>Journal des alertes</h2>
      {alerts.length === 0 ? (
        <div className="empty">Aucune alerte reçue</div>
      ) : (
        <ul className="feed">
          {alerts.map((a) => {
            const st = a.state === "off" ? "good" : severityStatus(a.severity);
            const val = fmtValue(a);
            return (
              <li key={a.id}>
                <StatusBadge status={st} compact label={a.state === "off" ? "Fin" : undefined} />
                <div>
                  <div className="feed-title">
                    {ALERT_TYPE_LABEL[a.type] ?? a.type}
                    {val && <span className="muted"> · {val}</span>}
                  </div>
                  <div className="muted small">
                    {SOURCE_LABEL[a.source] ?? a.source} · {a.device_id} · {a.severity}
                  </div>
                </div>
                <time className="muted small" dateTime={a.ts}>
                  {fmtTime(a.ts)}
                </time>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
