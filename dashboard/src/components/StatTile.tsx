import type { CSSProperties } from "react";
import type { Status } from "../lib/status";
import { StatusBadge } from "./StatusBadge";

interface Props {
  label: string;
  value?: number | null;
  text?: string;
  unit?: string;
  decimals?: number;
  status: Status;
  color: string;
  hint?: string;
}

export function StatTile({ label, value, text, unit, decimals = 1, status, color, hint }: Props) {
  const shown = text ?? (value === null || value === undefined ? "—" : value.toFixed(decimals));
  return (
    <div className="card tile" style={{ "--mark": color } as CSSProperties}>
      <div className="tile-head">
        <span className="mark" aria-hidden="true" />
        <span className="label">{label}</span>
      </div>
      <div className="value">
        {shown}
        {unit && shown !== "—" && <span className="unit">{unit}</span>}
      </div>
      <div className="tile-foot">
        <StatusBadge status={status} />
        {hint && <span className="hint muted small">{hint}</span>}
      </div>
    </div>
  );
}
