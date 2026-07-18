import type { AuditTrailEntry } from "../api";

export function AuditTrail({ entries }: { entries: AuditTrailEntry[] }) {
  if (entries.length === 0) return <div className="empty-state">No audit trail entries yet.</div>;
  return (
    <table>
      <thead>
        <tr><th>Timestamp</th><th>Entity</th><th>Action</th><th>Actor</th></tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.id}>
            <td>{new Date(e.timestamp + "Z").toLocaleString()}</td>
            <td>{e.entity_type} <span style={{ color: "var(--text-dim)" }}>{e.entity_id}</span></td>
            <td>{e.action}</td>
            <td>{e.actor_user_id ?? "system"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
