import type { Worker, Zone } from "../api";
import { WorkerRoster } from "./WorkerRoster";

export function SitePanel({ zones, workers }: { zones: Zone[]; workers: Worker[] }) {
  return (
    <>
      <div className="panel">
        <h2>Zones</h2>
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Risk category</th></tr></thead>
          <tbody>
            {zones.map((z) => (
              <tr key={z.id}>
                <td>{z.name}</td>
                <td>{z.zone_type.replace("_", " ")}</td>
                <td><span className={`badge ${z.risk_category}`}>{z.risk_category}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <h2>Worker roster</h2>
        <WorkerRoster workers={workers} />
      </div>
    </>
  );
}
