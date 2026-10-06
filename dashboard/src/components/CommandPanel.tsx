import { useState } from "react";
import { api, type CommandBody } from "../lib/api";
import type { Command } from "../lib/types";
import { ACTUATOR_LABEL, fmtTime } from "../lib/status";

interface BtnProps {
  label: string;
  body: CommandBody;
  kind?: "primary" | "danger";
  disabled: boolean;
  onSend: (label: string, body: CommandBody) => void;
}

function CmdButton({ label, body, kind, disabled, onSend }: BtnProps) {
  return (
    <button className={`btn${kind ? ` ${kind}` : ""}`} disabled={disabled} onClick={() => onSend(label, body)}>
      {label}
    </button>
  );
}

export function CommandPanel({ commands }: { commands: Command[] }) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);

  const send = async (label: string, body: CommandBody) => {
    setBusy(true);
    try {
      const c = await api.sendCommand(body);
      setFeedback({
        ok: c.published,
        text: c.published
          ? `${label} : transmis au boîtier (${c.cmd_id})`
          : `${label} : enregistré mais non transmis, broker hors ligne`,
      });
    } catch (e) {
      setFeedback({ ok: false, text: `${label} : échec (${e instanceof Error ? e.message : String(e)})` });
    } finally {
      setBusy(false);
    }
  };

  const groups: Array<{ name: string; buttons: Array<Omit<BtnProps, "disabled" | "onSend">> }> = [
    {
      name: "Buzzer",
      buttons: [
        { label: "Sirène 3 s", body: { actuator: "buzzer", action: "pulse", duration_ms: 3000 }, kind: "danger" },
        { label: "Marche", body: { actuator: "buzzer", action: "on" } },
        { label: "Silence", body: { actuator: "buzzer", action: "off" } },
      ],
    },
    {
      name: "LED rouge",
      buttons: [
        { label: "Allumer", body: { actuator: "led_red", action: "on" } },
        { label: "Clignoter 5 s", body: { actuator: "led_red", action: "blink", duration_ms: 5000 } },
        { label: "Auto", body: { actuator: "led_red", action: "off" } },
      ],
    },
    {
      name: "LED verte",
      buttons: [
        { label: "Allumer", body: { actuator: "led_green", action: "on" } },
        { label: "Clignoter 5 s", body: { actuator: "led_green", action: "blink", duration_ms: 5000 } },
        { label: "Auto", body: { actuator: "led_green", action: "off" } },
      ],
    },
  ];

  return (
    <section className="card">
      <h2>Panneau de commande</h2>
      {groups.map((g) => (
        <div className="cmd-group" key={g.name}>
          <div className="cmd-label">{g.name}</div>
          <div className="cmd-btns">
            {g.buttons.map((b) => (
              <CmdButton key={b.label} {...b} disabled={busy} onSend={send} />
            ))}
          </div>
        </div>
      ))}
      <div className="cmd-group">
        <div className="cmd-label">Tout</div>
        <div className="cmd-btns">
          <CmdButton label="Test complet" body={{ actuator: "led", action: "blink", duration_ms: 3000 }} kind="primary" disabled={busy} onSend={send} />
          <CmdButton label="Retour auto" body={{ actuator: "led", action: "off" }} disabled={busy} onSend={send} />
        </div>
      </div>
      {feedback && (
        <div className={`cmd-feedback ${feedback.ok ? "ok" : "ko"}`} role="status">
          {feedback.text}
        </div>
      )}
      <h3>Dernières commandes</h3>
      {commands.length === 0 ? (
        <div className="empty">Aucune commande envoyée</div>
      ) : (
        <ul className="feed compact">
          {commands.slice(0, 5).map((c) => (
            <li key={c.id}>
              <span>
                {ACTUATOR_LABEL[c.actuator] ?? c.actuator} · {c.action}
                {c.duration_ms ? ` · ${c.duration_ms} ms` : ""}
              </span>
              <span className="muted small">
                {c.published ? "publié" : "non publié"} · {fmtTime(c.ts)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
