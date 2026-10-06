import { useState } from "react";
import type { Detection, Prediction } from "../lib/types";
import { fmtTime } from "../lib/status";
import { StatusBadge } from "./StatusBadge";

interface Props {
  detections: Detection[];
  prediction: Prediction | null;
}

export function AiPanel({ detections, prediction }: Props) {
  const videoUrl = (import.meta.env.VITE_VIDEO_URL as string | undefined) ?? "";
  const [videoOk, setVideoOk] = useState(videoUrl !== "");
  const last = detections[0];

  return (
    <section className="card">
      <h2>Intelligence artificielle locale</h2>
      <div className="video">
        {videoUrl && videoOk ? (
          <img src={videoUrl} alt="Flux webcam analysé par l'IA" onError={() => setVideoOk(false)} />
        ) : (
          <div className="video-empty">
            Flux vidéo indisponible
            <span className="small">lancer ai/vision.py puis renseigner VITE_VIDEO_URL</span>
          </div>
        )}
      </div>
      <div className="ai-grid">
        <div>
          <div className="label">Dernière détection</div>
          {last ? (
            <>
              <div className="value-sm">
                {last.label} <span className="muted">{Math.round(last.confidence * 100)} %</span>
              </div>
              <div className="meter" aria-hidden="true">
                <i style={{ width: `${Math.round(last.confidence * 100)}%` }} />
              </div>
              <div className="muted small">
                {fmtTime(last.ts)} · {last.source}
              </div>
            </>
          ) : (
            <div className="muted">aucune détection</div>
          )}
        </div>
        <div>
          <div className="label">Maintenance prédictive</div>
          {prediction ? (
            <>
              <StatusBadge status={prediction.is_anomaly ? "critical" : "good"} label={prediction.is_anomaly ? "Anomalie" : "Normal"} />
              <div className="muted small">
                score {prediction.score.toFixed(3)} · {prediction.model} · {fmtTime(prediction.ts)}
              </div>
            </>
          ) : (
            <div className="muted">aucune prédiction</div>
          )}
        </div>
      </div>
      {detections.length > 1 && (
        <ul className="feed compact">
          {detections.slice(1, 6).map((d) => (
            <li key={d.id}>
              <span>
                {d.label} · {Math.round(d.confidence * 100)} %
              </span>
              <span className="muted small">{fmtTime(d.ts)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
