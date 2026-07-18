import type { BillingSummary } from "../api";

export function BillingPanel({ billing }: { billing: BillingSummary | null }) {
  if (!billing) return <div className="empty-state">Billing summary is admin-only.</div>;
  return (
    <div className="panel">
      <h2>Usage-based billing — {billing.plan_name} plan</h2>
      <table>
        <tbody>
          <tr><td>Base fee</td><td>${billing.base_fee.toFixed(2)}</td></tr>
          <tr><td>Cameras metered ({billing.camera_count} × ${billing.camera_unit_price})</td><td>${(billing.camera_count * billing.camera_unit_price).toFixed(2)}</td></tr>
          <tr><td>IoT sensors metered ({billing.sensor_count} × ${billing.sensor_unit_price})</td><td>${(billing.sensor_count * billing.sensor_unit_price).toFixed(2)}</td></tr>
          <tr style={{ fontWeight: 700 }}><td>Estimated total this period</td><td>${billing.estimated_total.toFixed(2)}</td></tr>
        </tbody>
      </table>
    </div>
  );
}
