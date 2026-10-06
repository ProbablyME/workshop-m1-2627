import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Palette } from "../lib/theme";
import { fmtTime } from "../lib/status";

export interface Point {
  t: number;
  v: number | null;
}

export interface Threshold {
  value: number;
  label: string;
  level: "warning" | "critical";
}

interface Props {
  title: string;
  unit: string;
  data: Point[];
  color: string;
  pal: Palette;
  decimals?: number;
  thresholds?: Threshold[];
  domain?: [number | "auto", number | "auto"];
}

// Une série par graphique (jamais de double axe). Ligne 2 px, grille hairline, curseur vertical,
// dernière valeur en clair et vue tableau : les valeurs restent lisibles sans survol ni couleur.
export function TimeSeriesChart({ title, unit, data, color, pal, decimals = 1, thresholds = [], domain = ["auto", "auto"] }: Props) {
  const [table, setTable] = useState(false);
  const last = useMemo(() => [...data].reverse().find((p) => p.v !== null), [data]);
  // Sur une fenêtre courte (< 8 min) les ticks à la minute se répètent : on affiche les secondes.
  const spanMs = data.length > 1 ? data[data.length - 1].t - data[0].t : 0;
  const withSeconds = spanMs < 8 * 60_000;
  const rows = useMemo(() => data.slice(-15).reverse(), [data]);

  return (
    <section className="card chart" aria-label={title}>
      <div className="chart-head">
        <h2>
          <span className="mark" style={{ background: color }} aria-hidden="true" />
          {title}
        </h2>
        <div className="chart-tools">
          {last && (
            <span className="last">
              {last.v!.toFixed(decimals)} {unit}
              <span className="muted"> · {fmtTime(last.t)}</span>
            </span>
          )}
          <button className="btn small" aria-pressed={table} onClick={() => setTable((t) => !t)}>
            {table ? "Courbe" : "Tableau"}
          </button>
        </div>
      </div>

      {table ? (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th className="l">Heure</th>
                <th>{unit}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.t}>
                  <td className="l">{fmtTime(p.t)}</td>
                  <td>{p.v === null ? "—" : p.v.toFixed(decimals)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : data.length === 0 ? (
        <div className="empty">En attente de télémétrie…</div>
      ) : (
        <div className="plot">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke={pal.grid} strokeWidth={1} />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(t: number) => fmtTime(t, withSeconds)}
                tick={{ fill: pal.muted, fontSize: 11 }}
                axisLine={{ stroke: pal.axis }}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis domain={domain} width={44} tick={{ fill: pal.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
              {thresholds.map((th) => (
                <ReferenceLine
                  key={th.label}
                  y={th.value}
                  stroke={th.level === "critical" ? pal.critical : pal.warning}
                  strokeDasharray="4 3"
                  label={{ value: th.label, position: "insideTopRight", fill: pal.muted, fontSize: 11 }}
                />
              ))}
              <Tooltip
                cursor={{ stroke: pal.axis, strokeWidth: 1 }}
                isAnimationActive={false}
                content={<ChartTip unit={unit} decimals={decimals} color={color} title={title} />}
              />
              <Line
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 5, fill: color, stroke: pal.surface, strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

interface TipProps {
  active?: boolean;
  payload?: Array<{ value?: number | string | null }>;
  label?: number | string;
  unit: string;
  decimals: number;
  color: string;
  title: string;
}

function ChartTip({ active, payload, label, unit, decimals, color, title }: TipProps) {
  if (!active || !payload || payload.length === 0 || label === undefined) return null;
  const v = payload[0]?.value;
  const shown = v === null || v === undefined ? "—" : `${Number(v).toFixed(decimals)} ${unit}`;
  return (
    <div className="tip">
      <div className="v">{shown}</div>
      <div className="l">
        <span className="k" style={{ background: color }} aria-hidden="true" />
        {title} · {fmtTime(Number(label))}
      </div>
    </div>
  );
}
