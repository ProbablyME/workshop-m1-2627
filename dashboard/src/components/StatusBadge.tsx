import { STATUS_ICON, STATUS_LABEL, type Status } from "../lib/status";

interface Props {
  status: Status;
  label?: string;
  compact?: boolean;
  title?: string;
}

// Icône + libellé + pastille : l'état ne repose jamais sur la couleur seule.
export function StatusBadge({ status, label, compact, title }: Props) {
  return (
    <span className={`badge${compact ? " compact" : ""}`} data-status={status} title={title}>
      <span className="dot" aria-hidden="true" />
      <span className="ic" aria-hidden="true">{STATUS_ICON[status]}</span>
      <span className="badge-label">{label ?? STATUS_LABEL[status]}</span>
    </span>
  );
}
