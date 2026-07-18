import { useState } from "react";
import { api, type EmrSummary, type IncidentBonus } from "../api";

export function EmrPanel({
  emr,
  bonuses,
  onChanged,
}: {
  emr: EmrSummary | null;
  bonuses: IncidentBonus[];
  onChanged: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);

  async function act(id: string, status: "verified" | "disputed" | "rejected") {
    setBusyId(id);
    try {
      await api.verifyBonus(id, status);
      onChanged();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="panel">
        <h2>EMR / insurer analytics</h2>
        <p style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 0 }}>
          Estimated figures are prototype placeholders, not actuarial data — see the build spec's closing note.
        </p>
        {emr && (
          <div className="kpi-row" style={{ marginBottom: 0 }}>
            <div className="kpi-card"><div className="label">Incidents prevented</div><div className="value">{emr.incidents_prevented_count}</div></div>
            <div className="kpi-card"><div className="label">Est. bonus total</div><div className="value">${emr.estimated_bonus_total.toFixed(0)}</div></div>
            <div className="kpi-card"><div className="label">Resolved risk events</div><div className="value">{emr.resolved_risk_events}</div></div>
            <div className="kpi-card high"><div className="label">Open high/critical</div><div className="value">{emr.open_high_critical_risk_events}</div></div>
            <div className="kpi-card"><div className="label">EMR delta (proxy)</div><div className="value">{emr.computed_emr_delta > 0 ? "+" : ""}{emr.computed_emr_delta}</div></div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Incident-prevention bonuses (requires human review before payout)</h2>
        {bonuses.length === 0 ? (
          <div className="empty-state">No bonus records yet — resolve a high/critical risk event that matched an OSHA pattern to generate one.</div>
        ) : (
          <table>
            <thead><tr><th>Pattern avoided</th><th>Est. amount</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {bonuses.map((b) => (
                <tr key={b.id}>
                  <td>{b.estimated_severity_avoided}</td>
                  <td>${b.bonus_amount.toFixed(2)}</td>
                  <td><span className="badge status">{b.verification_status}</span></td>
                  <td>
                    {b.verification_status === "pending" ? (
                      <div style={{ display: "flex", gap: 6 }}>
                        <button disabled={busyId === b.id} onClick={() => act(b.id, "verified")}>Verify</button>
                        <button disabled={busyId === b.id} onClick={() => act(b.id, "disputed")}>Dispute</button>
                        <button disabled={busyId === b.id} onClick={() => act(b.id, "rejected")}>Reject</button>
                      </div>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
