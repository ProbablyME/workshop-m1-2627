import { useMemo, useState } from "react";
import { AiPanel } from "./components/AiPanel";
import { AlertsFeed } from "./components/AlertsFeed";
import { CommandPanel } from "./components/CommandPanel";
import { StatTile } from "./components/StatTile";
import { TimeSeriesChart, type Point } from "./components/TimeSeriesChart";
import { TopBar } from "./components/TopBar";
import { gasAlertStatus, humStatus, motionStatus, tempStatus, THRESHOLDS } from "./lib/status";
import { palette, useMode } from "./lib/theme";
import type { Telemetry } from "./lib/types";
import { useLiveData } from "./lib/useLiveData";

const RANGES = [
  { min: 15, label: "15 min" },
  { min: 30, label: "30 min" },
  { min: 60, label: "1 h" },
  { min: 120, label: "2 h" },
];

function series(rows: Telemetry[], key: "temperature" | "humidity" | "gas_raw"): Point[] {
  return rows.map((t) => ({ t: new Date(t.ts).getTime(), v: t[key] }));
}

export default function App() {
  const [mode, toggleMode] = useMode();
  const pal = palette[mode];
  const live = useLiveData();
  const [range, setRange] = useState(30);

  const windowed = useMemo(() => {
    const since = Date.now() - range * 60_000;
    return live.telemetry.filter((t) => new Date(t.ts).getTime() >= since);
  }, [live.telemetry, range]);

  const latest = live.telemetry[live.telemetry.length - 1] ?? null;
  const temp = latest?.temperature ?? null;
  const hum = latest?.humidity ?? null;
  const gas = latest?.gas_raw ?? null;

  return (
    <>
      <TopBar device={live.device} health={live.health} wsState={live.wsState} mode={mode} onToggleMode={toggleMode} />
      <main className="main">
        {live.loadError && (
          <div className="banner ko" role="alert">
            API injoignable : {live.loadError}
            <button className="btn small" onClick={live.refresh}>
              Réessayer
            </button>
          </div>
        )}

        <div className="filters">
          <span className="muted">Fenêtre</span>
          <div className="seg" role="group" aria-label="Fenêtre temporelle">
            {RANGES.map((r) => (
              <button key={r.min} className="btn small" aria-pressed={range === r.min} onClick={() => setRange(r.min)}>
                {r.label}
              </button>
            ))}
          </div>
          <span className="muted small">{windowed.length} mesures</span>
        </div>

        <section className="kpis" aria-label="Indicateurs">
          <StatTile label="Température" value={temp} unit="°C" status={tempStatus(temp)} color={pal.temp} hint={`seuils ${THRESHOLDS.temp.warn} / ${THRESHOLDS.temp.crit} °C`} />
          <StatTile label="Humidité" value={hum} unit="%" decimals={0} status={humStatus(hum)} color={pal.hum} hint={`seuils ${THRESHOLDS.hum.warn} / ${THRESHOLDS.hum.crit} %`} />
          <StatTile
            label="Gaz / fumée"
            value={gas}
            unit="raw"
            decimals={0}
            status={gasAlertStatus(live.alerts)}
            color={pal.gas}
            hint="alerte si hausse de 80 / 200 sur la ligne de base"
          />
          <StatTile
            label="Présence (PIR)"
            text={latest ? (latest.motion ? "Détectée" : "Aucune") : "—"}
            status={motionStatus(latest ? latest.motion : null)}
            color={pal.muted}
            hint={latest?.rssi != null ? `Wi-Fi ${latest.rssi} dBm` : undefined}
          />
        </section>

        <section className="charts" aria-label="Courbes">
          <TimeSeriesChart
            title="Température"
            unit="°C"
            data={series(windowed, "temperature")}
            color={pal.temp}
            pal={pal}
            thresholds={[
              { value: THRESHOLDS.temp.warn, label: "attention", level: "warning" },
              { value: THRESHOLDS.temp.crit, label: "critique", level: "critical" },
            ]}
          />
          <TimeSeriesChart title="Humidité" unit="%" data={series(windowed, "humidity")} color={pal.hum} pal={pal} decimals={0} domain={[0, 100]} />
          <TimeSeriesChart
            title="Gaz / fumée (MQ-2)"
            unit="raw"
            data={series(windowed, "gas_raw")}
            color={pal.gas}
            pal={pal}
            decimals={0}
            domain={[0, 1023]}
          />
        </section>

        <section className="panels" aria-label="Alertes, commandes, IA">
          <AlertsFeed alerts={live.alerts} />
          <CommandPanel commands={live.commands} />
          <AiPanel detections={live.detections} prediction={live.prediction} />
        </section>

        <footer className="muted small">
          Sentinel-X · API {live.health?.version ?? "?"} · {live.health?.ws_clients ?? 0} client(s) temps réel · {live.telemetry.length} mesures en mémoire
        </footer>
      </main>
    </>
  );
}
