import { useState } from "react";
import { api, type CalibrationLogEntry, type OnboardingChecklist } from "../api";

const STAGES: { key: string; label: string; day: string }[] = [
  { key: "inventory", label: "Inventory & zones", day: "Day 1" },
  { key: "calibration", label: "Live calibration", day: "Day 2" },
  { key: "routing", label: "Alert routing & dry run", day: "Day 3" },
  { key: "live", label: "Signed off & live", day: "Go-live" },
];

export function OnboardingPanel({
  checklist,
  calibrationLog,
  onChanged,
  siteId,
}: {
  checklist: OnboardingChecklist | null;
  calibrationLog: CalibrationLogEntry[];
  onChanged: () => void;
  siteId: string;
}) {
  const [thresholdType, setThresholdType] = useState("ppe_confidence_min");
  const [oldValue, setOldValue] = useState("0.6");
  const [newValue, setNewValue] = useState("0.7");
  const [justification, setJustification] = useState("");
  const [busy, setBusy] = useState(false);

  async function submitCalibration(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createCalibrationEntry(siteId, { threshold_type: thresholdType, old_value: oldValue, new_value: newValue, justification });
      setJustification("");
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function advance(stage: string) {
    setBusy(true);
    try {
      await api.advanceOnboarding(siteId, stage, `Advanced to ${stage} from dashboard`);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  if (!checklist) return null;
  const currentIndex = STAGES.findIndex((s) => s.key === checklist.stage);

  return (
    <div>
      <div className="panel">
        <h2>Onboarding & calibration (§9 — 2-3 day flow)</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {STAGES.map((s, i) => (
            <div key={s.key} style={{
              flex: 1, padding: "10px 12px", borderRadius: 8,
              border: `1px solid ${i === currentIndex ? "var(--accent)" : "var(--border)"}`,
              background: i <= currentIndex ? "var(--panel-alt)" : "transparent",
              opacity: i <= currentIndex ? 1 : 0.5,
            }}>
              <div style={{ fontSize: 11, color: "var(--text-dim)" }}>{s.day}</div>
              <div style={{ fontSize: 13, fontWeight: i === currentIndex ? 700 : 400 }}>{s.label}</div>
            </div>
          ))}
        </div>
        <table>
          <tbody>
            <tr><td>Cameras inventoried</td><td>{checklist.camera_count}</td></tr>
            <tr><td>Zones drawn</td><td>{checklist.zone_count}</td></tr>
            <tr><td>PPE requirements mapped</td><td>{checklist.ppe_requirement_count}</td></tr>
            <tr><td>Calibration entries logged</td><td>{checklist.calibration_entries}</td></tr>
            <tr><td>Users assigned to site</td><td>{checklist.users_assigned}</td></tr>
          </tbody>
        </table>
        <div className="actions" style={{ marginTop: 12 }}>
          {STAGES.map((s, i) => (
            <button
              key={s.key}
              className={i === currentIndex + 1 ? "primary" : undefined}
              disabled={busy || i <= currentIndex || !checklist.ready_for_next_stage}
              onClick={() => advance(s.key)}
            >
              Advance to {s.label}
            </button>
          ))}
        </div>
        {!checklist.ready_for_next_stage && (
          <p className="error-text" style={{ marginTop: 8 }}>Complete the current stage's checklist items before advancing.</p>
        )}
      </div>

      <div className="panel">
        <h2>Log a threshold calibration</h2>
        <form onSubmit={submitCalibration} className="simulate-form">
          <div className="field">
            <label>Threshold type</label>
            <input value={thresholdType} onChange={(e) => setThresholdType(e.target.value)} />
          </div>
          <div className="field">
            <label>Old value</label>
            <input value={oldValue} onChange={(e) => setOldValue(e.target.value)} style={{ width: 70 }} />
          </div>
          <div className="field">
            <label>New value</label>
            <input value={newValue} onChange={(e) => setNewValue(e.target.value)} style={{ width: 70 }} />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Justification</label>
            <input value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Why is this changing?" required style={{ width: "100%" }} />
          </div>
          <button type="submit" className="primary" disabled={busy}>Log calibration</button>
        </form>
      </div>

      <div className="panel">
        <h2>Calibration log</h2>
        {calibrationLog.length === 0 ? <div className="empty-state">No calibration changes logged yet.</div> : (
          <table>
            <thead><tr><th>Changed</th><th>Threshold</th><th>Old → New</th><th>Justification</th></tr></thead>
            <tbody>
              {calibrationLog.map((c) => (
                <tr key={c.id}>
                  <td>{new Date(c.changed_at + "Z").toLocaleString()}</td>
                  <td>{c.threshold_type}</td>
                  <td>{c.old_value} → {c.new_value}</td>
                  <td>{c.justification}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
