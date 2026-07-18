import { useState } from "react";
import { api, type RiskEvent } from "../api";

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso + "Z").getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function RiskEventList({ events, onChanged }: { events: RiskEvent[]; onChanged: () => void }) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [interventionDraft, setInterventionDraft] = useState<Record<string, string>>({});

  async function run(id: string, fn: () => Promise<unknown>) {
    setBusyId(id);
    try {
      await fn();
      onChanged();
    } finally {
      setBusyId(null);
    }
  }

  if (events.length === 0) {
    return <div className="empty-state">No risk events yet — simulate a detection to see the pipeline in action.</div>;
  }

  return (
    <div>
      {events.map((event) => (
        <div className="event-row" key={event.id}>
          <div className={`score badge ${event.risk_category}`} style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
            {event.risk_score}
          </div>
          <div className="body">
            <div>
              <span className={`badge ${event.risk_category}`}>{event.risk_category}</span>{" "}
              <span className="badge status">{event.status.replace("_", " ")}</span>
            </div>
            <div className="explanation">{event.explanation}</div>
            <div className="meta">
              <span>{timeAgo(event.created_at)}</span>
              {event.intervention_notes && <span>Intervention: {event.intervention_notes}</span>}
            </div>
            {event.status !== "resolved" && event.status !== "false_positive" && (
              <div className="actions">
                {event.status === "open" && (
                  <button disabled={busyId === event.id} onClick={() => run(event.id, () => api.acknowledgeRiskEvent(event.id))}>
                    Acknowledge
                  </button>
                )}
                {(event.status === "open" || event.status === "acknowledged") && (
                  <>
                    <input
                      placeholder="Log intervention..."
                      style={{ fontSize: 12, padding: "5px 8px" }}
                      value={interventionDraft[event.id] ?? ""}
                      onChange={(e) => setInterventionDraft((d) => ({ ...d, [event.id]: e.target.value }))}
                    />
                    <button
                      disabled={busyId === event.id || !interventionDraft[event.id]}
                      onClick={() => run(event.id, () => api.logIntervention(event.id, interventionDraft[event.id]))}
                    >
                      Log
                    </button>
                  </>
                )}
                <button disabled={busyId === event.id} onClick={() => run(event.id, () => api.resolveRiskEvent(event.id, "resolved"))}>
                  Resolve
                </button>
                <button disabled={busyId === event.id} onClick={() => run(event.id, () => api.resolveRiskEvent(event.id, "false_positive"))}>
                  False positive
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
