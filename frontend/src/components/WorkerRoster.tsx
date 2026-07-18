import type { Worker } from "../api";

export function WorkerRoster({ workers }: { workers: Worker[] }) {
  if (workers.length === 0) return <div className="empty-state">No workers on roster.</div>;
  return (
    <table>
      <thead>
        <tr><th>Name</th><th>Trade</th><th>Badge</th><th>Status</th></tr>
      </thead>
      <tbody>
        {workers.map((w) => (
          <tr key={w.id}>
            <td>{w.name}</td>
            <td>{w.trade}</td>
            <td>{w.badge_id}</td>
            <td>{w.active ? "Active" : "Inactive"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
