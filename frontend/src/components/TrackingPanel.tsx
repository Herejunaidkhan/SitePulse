import { useState } from "react";
import { api, type DwellTimeEntry, type Worker, type Zone } from "../api";

export function TrackingPanel({
  siteId,
  workers,
  zones,
  dwellTime,
  onRefresh,
}: {
  siteId: string;
  workers: Worker[];
  zones: Zone[];
  dwellTime: DwellTimeEntry[];
  onRefresh: () => void;
}) {
  const [workerId, setWorkerId] = useState(workers[0]?.id ?? "");
  const [zoneId, setZoneId] = useState("");
  const [busy, setBusy] = useState(false);
  const [vitalsBusy, setVitalsBusy] = useState(false);
  const [proxBusy, setProxBusy] = useState(false);

  async function pingLocation() {
    if (!workerId) return;
    setBusy(true);
    try {
      await api.simulateLocationPing(siteId, workerId, zoneId || undefined);
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function pingVitals() {
    if (!workerId) return;
    setVitalsBusy(true);
    try {
      await api.simulateSensorReading(siteId, {
        sensor_type: "vitals",
        worker_id: workerId,
        value: { heart_rate: 125 + Math.round(Math.random() * 25), shift_minutes: 400 + Math.round(Math.random() * 200) },
      });
      onRefresh();
    } finally {
      setVitalsBusy(false);
    }
  }

  async function pingProximity() {
    setProxBusy(true);
    try {
      await api.simulateSensorReading(siteId, { sensor_type: "proximity", value: { distance_m: Math.round(Math.random() * 40) / 10 } });
      onRefresh();
    } finally {
      setProxBusy(false);
    }
  }

  const maxPings = Math.max(...dwellTime.map((d) => d.ping_count), 1);

  return (
    <div>
      <div className="panel">
        <h2>Simulate wearable / IoT signal</h2>
        <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 0 }}>
          Stands in for BLE/UWB wearable pings and IoT proximity/vitals sensors — feeds worker
          location trail, the proximity ground-truth check, and the fatigue proxy used in scoring.
        </p>
        <div className="simulate-form">
          <div className="field">
            <label>Worker</label>
            <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
              {workers.map((w) => (
                <option key={w.id} value={w.id}>{w.name} ({w.trade})</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Zone (location ping)</label>
            <select value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
              <option value="">Random</option>
              {zones.map((z) => (
                <option key={z.id} value={z.id}>{z.name}</option>
              ))}
            </select>
          </div>
          <button disabled={busy} onClick={pingLocation}>Simulate location ping</button>
          <button disabled={vitalsBusy} onClick={pingVitals}>Simulate elevated vitals reading</button>
          <button disabled={proxBusy} onClick={pingProximity}>Simulate close proximity reading</button>
        </div>
      </div>

      <div className="panel">
        <h2>Dwell time by zone (last 24h)</h2>
        {dwellTime.length === 0 ? (
          <div className="empty-state">No location pings recorded yet.</div>
        ) : (
          dwellTime.map((d) => (
            <div className="zone-heat-row" key={d.zone_id}>
              <div className="name">{d.zone_name}</div>
              <div className="zone-heat-bar-track">
                <div className="zone-heat-bar-fill" style={{ width: `${(d.ping_count / maxPings) * 100}%`, background: "var(--accent)" }} />
              </div>
              <div className="val">{d.ping_count} ping(s)</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
