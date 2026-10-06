import type { Device, Health } from "../lib/types";
import type { WsState } from "../lib/useLiveData";
import type { Mode } from "../lib/theme";
import { fmtAgo } from "../lib/status";
import { StatusBadge } from "./StatusBadge";

interface Props {
  device: Device | null;
  health: Health | null;
  wsState: WsState;
  mode: Mode;
  onToggleMode: () => void;
}

export function TopBar({ device, health, wsState, mode, onToggleMode }: Props) {
  const online = device?.online ?? false;
  const deviceDetail = device
    ? `${device.id} · ${device.ip ?? "IP inconnue"} · fw ${device.fw ?? "?"} · vu ${fmtAgo(device.last_seen)}`
    : "aucun boîtier enregistré";
  const mqttOk = health?.mqtt_connected ?? false;

  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">A</span>
        <div>
          <div className="brand-title">SENTINEL-X · Centre de Commandement Tactique</div>
          <div className="brand-sub">AetherCorp Industrial Solutions · Consortium Groupe 1</div>
        </div>
      </div>
      <div className="statusbar">
        <StatusBadge status={online ? "good" : "critical"} label={online ? "Boîtier en ligne" : "Boîtier hors ligne"} title={deviceDetail} />
        <StatusBadge
          status={health ? (mqttOk ? "good" : "critical") : "neutral"}
          label={health ? (mqttOk ? "Broker MQTT" : "Broker coupé") : "API injoignable"}
          title={health ? `API ${health.version} · base ${health.db_ok ? "OK" : "KO"}` : "pas de réponse de /api/v1/health"}
        />
        <StatusBadge
          status={wsState === "open" ? "good" : wsState === "connecting" ? "warning" : "critical"}
          label={wsState === "open" ? "Temps réel" : wsState === "connecting" ? "Connexion…" : "Reconnexion"}
          title="WebSocket /ws"
        />
        <span className="device-detail muted small">{deviceDetail}</span>
        <button className="btn small" onClick={onToggleMode} aria-label="Changer de thème">
          {mode === "dark" ? "Thème clair" : "Thème sombre"}
        </button>
      </div>
    </header>
  );
}
