import type { ZoneHeat as ZoneHeatEntry } from "../api";

function colorFor(score: number): string {
  if (score >= 75) return "var(--critical)";
  if (score >= 50) return "var(--high)";
  if (score >= 25) return "var(--medium)";
  return "var(--low)";
}

export function ZoneHeat({ zones }: { zones: ZoneHeatEntry[] }) {
  if (zones.length === 0) {
    return <div className="empty-state">No open risk in any zone right now.</div>;
  }
  return (
    <div>
      {zones
        .slice()
        .sort((a, b) => b.avg_risk_score - a.avg_risk_score)
        .map((zone) => (
          <div className="zone-heat-row" key={zone.zone_id}>
            <div className="name">{zone.zone_name}</div>
            <div className="zone-heat-bar-track">
              <div
                className="zone-heat-bar-fill"
                style={{ width: `${zone.avg_risk_score}%`, background: colorFor(zone.avg_risk_score) }}
              />
            </div>
            <div className="val">{zone.avg_risk_score}/100 · {zone.open_count} open</div>
          </div>
        ))}
    </div>
  );
}
