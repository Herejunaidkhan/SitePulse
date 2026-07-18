import { useState } from "react";
import { api, ApiError, type Worker, type Zone } from "../api";

const DETECTION_TYPES = [
  { value: "", label: "Random" },
  { value: "ppe_violation", label: "PPE violation" },
  { value: "proximity", label: "Unsafe proximity" },
  { value: "fall_risk_posture", label: "Fall-risk posture" },
  { value: "unguarded_edge", label: "Unguarded edge" },
];

export function SimulatePanel({
  siteId,
  zones,
  workers,
  onSimulated,
}: {
  siteId: string;
  zones: Zone[];
  workers: Worker[];
  onSimulated: (result: { riskScore: number; riskCategory: string; alertsCreated: number }) => void;
}) {
  const [detectionType, setDetectionType] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [confidence, setConfidence] = useState(0.85);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function simulate() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.simulateDetection(siteId, {
        detection_type: detectionType || undefined,
        zone_id: zoneId || undefined,
        worker_id: workerId || undefined,
        confidence_score: confidence,
      });
      onSimulated({
        riskScore: result.risk_event.risk_score,
        riskCategory: result.risk_event.risk_category,
        alertsCreated: result.alerts_created,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 0 }}>
        Stands in for the CV inference service — generates a synthetic detection so you can see the
        full detect → score → alert pipeline run end to end. A real model plugs in behind the same interface.
      </p>
      <div className="simulate-form">
        <div className="field">
          <label>Detection type</label>
          <select value={detectionType} onChange={(e) => setDetectionType(e.target.value)}>
            {DETECTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Zone</label>
          <select value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
            <option value="">Random</option>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>{z.name} ({z.risk_category})</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Worker</label>
          <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
            <option value="">Random</option>
            {workers.map((w) => (
              <option key={w.id} value={w.id}>{w.name} ({w.trade})</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Confidence: {confidence.toFixed(2)}</label>
          <input type="range" min={0.4} max={0.99} step={0.01} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
        </div>
        <button className="primary" onClick={simulate} disabled={loading}>
          {loading ? "Running inference..." : "Simulate detection"}
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
