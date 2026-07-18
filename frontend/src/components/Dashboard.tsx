import { useCallback, useEffect, useState } from "react";
import {
  api,
  setToken,
  type AuditTrailEntry,
  type AuditVerifyResult,
  type BillingSummary,
  type CalibrationLogEntry,
  type DashboardSummary,
  type DwellTimeEntry,
  type EmrSummary,
  type IncidentBonus,
  type OnboardingChecklist as OnboardingChecklistType,
  type RiskEvent,
  type Site,
  type User,
  type Worker,
  type Zone,
} from "../api";
import { RiskEventList } from "./RiskEventList";
import { ZoneHeat } from "./ZoneHeat";
import { SimulatePanel } from "./SimulatePanel";
import { SitePanel } from "./SitePanel";
import { AuditTrail } from "./AuditTrail";
import { TrackingPanel } from "./TrackingPanel";
import { BillingPanel } from "./BillingPanel";
import { EmrPanel } from "./EmrPanel";
import { OnboardingPanel } from "./OnboardingPanel";
import { HazardIcon, GridIcon, AlertIcon, MapIcon, RadarIcon, ChecklistIcon, ShieldIcon, DollarIcon, LockIcon } from "./Icons";

type Tab = "overview" | "risk-events" | "site" | "tracking" | "onboarding" | "emr" | "billing" | "audit";

const NAV: { key: Tab; label: string; icon: (s?: { size?: number }) => JSX.Element; roles?: User["role"][] }[] = [
  { key: "overview", label: "Overview", icon: (p) => <GridIcon {...p} /> },
  { key: "risk-events", label: "Risk events", icon: (p) => <AlertIcon {...p} /> },
  { key: "site", label: "Site", icon: (p) => <MapIcon {...p} /> },
  { key: "tracking", label: "Tracking", icon: (p) => <RadarIcon {...p} /> },
  { key: "onboarding", label: "Onboarding", icon: (p) => <ChecklistIcon {...p} />, roles: ["admin", "safety_officer"] },
  { key: "emr", label: "EMR & insurer", icon: (p) => <ShieldIcon {...p} />, roles: ["admin", "safety_officer"] },
  { key: "billing", label: "Billing", icon: (p) => <DollarIcon {...p} />, roles: ["admin"] },
  { key: "audit", label: "Audit trail", icon: (p) => <LockIcon {...p} /> },
];

export function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [sites, setSites] = useState<Site[]>([]);
  const [site, setSite] = useState<Site | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [riskEvents, setRiskEvents] = useState<RiskEvent[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditTrailEntry[]>([]);
  const [dwellTime, setDwellTime] = useState<DwellTimeEntry[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [emr, setEmr] = useState<EmrSummary | null>(null);
  const [bonuses, setBonuses] = useState<IncidentBonus[]>([]);
  const [calibrationLog, setCalibrationLog] = useState<CalibrationLogEntry[]>([]);
  const [onboarding, setOnboarding] = useState<OnboardingChecklistType | null>(null);
  const [auditVerify, setAuditVerify] = useState<AuditVerifyResult | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const navItems = NAV.filter((n) => !n.roles || n.roles.includes(user.role));

  const refresh = useCallback(async (siteId: string) => {
    const [s, r, a, d, c, o] = await Promise.all([
      api.dashboardSummary(siteId),
      api.riskEvents(siteId),
      api.auditTrail(siteId),
      api.dwellTime(siteId),
      api.calibrationLog(siteId),
      api.onboardingChecklist(siteId),
    ]);
    setSummary(s);
    setRiskEvents(r);
    setAuditEntries(a);
    setDwellTime(d);
    setCalibrationLog(c);
    setOnboarding(o);

    if (user.role === "admin") {
      api.billingSummary().then(setBilling).catch(() => setBilling(null));
    }
    if (user.role === "admin" || user.role === "safety_officer") {
      api.emrSummary(user.org_id).then(setEmr).catch(() => setEmr(null));
      api.incidentBonuses(user.org_id).then(setBonuses).catch(() => setBonuses([]));
    }
  }, [user.role, user.org_id]);

  const selectSite = useCallback(async (s: Site) => {
    setSite(s);
    const [z, w] = await Promise.all([api.zones(s.id), api.workers(s.id)]);
    setZones(z);
    setWorkers(w);
    await refresh(s.id);
  }, [refresh]);

  useEffect(() => {
    (async () => {
      const allSites = await api.sites();
      setSites(allSites);
      if (allSites[0]) await selectSite(allSites[0]);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!site) return;
    const id = setInterval(() => refresh(site.id), 5000);
    return () => clearInterval(id);
  }, [site, refresh]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(id);
  }, [toast]);

  function logout() {
    setToken(null);
    onLogout();
  }

  if (!site) {
    return <div className="app-shell"><div className="content">Loading site...</div></div>;
  }

  return (
    <div className="app-shell">
      {toast && <div className="toast-banner">{toast}</div>}
      <div className="sidebar">
        <div className="brand">
          <div className="mark"><HazardIcon size={18} /></div>
          SitePulse
        </div>
        {navItems.map((n) => (
          <div key={n.key} className={`nav-item ${tab === n.key ? "active" : ""}`} onClick={() => setTab(n.key)}>
            {n.icon({ size: 16 })} {n.label}
          </div>
        ))}
        <div className="sidebar-footer">
          <div className="sidebar-user">{user.name}<br /><span className="role">{user.role.replace("_", " ")}</span></div>
          <button onClick={logout} style={{ width: "100%" }}>Sign out</button>
        </div>
      </div>

      <div className="main-area">
        <div className="topbar">
          <div className="site-picker">
            <select
              value={site.id}
              onChange={(e) => {
                const next = sites.find((s) => s.id === e.target.value);
                if (next) selectSite(next);
              }}
            >
              {sites.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <div className="site-meta">{site.address} · {sites.length} site(s) on this org</div>
          </div>
        </div>

        <div className="content">
          {summary && (
            <div className="kpi-row">
              <div className="kpi-card"><div className="label">Open risk events</div><div className="value">{summary.open_risk_events}</div></div>
              <div className="kpi-card critical"><div className="label">Critical</div><div className="value">{summary.critical_open}</div></div>
              <div className="kpi-card high"><div className="label">High</div><div className="value">{summary.high_open}</div></div>
              <div className="kpi-card"><div className="label">Alerts pending ack</div><div className="value">{summary.alerts_pending_ack}</div></div>
              <div className="kpi-card"><div className="label">Mean time to ack</div><div className="value">{summary.mean_time_to_ack_seconds ?? "—"}{summary.mean_time_to_ack_seconds ? "s" : ""}</div></div>
            </div>
          )}

          {tab === "overview" && (
            <>
              <div className="panel">
                <h2>Simulate a detection</h2>
                <SimulatePanel
                  siteId={site.id}
                  zones={zones}
                  workers={workers}
                  onSimulated={(r) => {
                    setToast(`New ${r.riskCategory} risk event (score ${r.riskScore}) — ${r.alertsCreated} alert(s) sent`);
                    refresh(site.id);
                  }}
                />
              </div>
              <div className="panel">
                <h2>Live risk heat by zone</h2>
                {summary && <ZoneHeat zones={summary.zone_heat} />}
              </div>
              <div className="panel">
                <h2>Recent risk events</h2>
                <RiskEventList events={riskEvents.slice(0, 8)} onChanged={() => refresh(site.id)} />
              </div>
            </>
          )}

          {tab === "risk-events" && (
            <div className="panel">
              <h2>All risk events</h2>
              <RiskEventList events={riskEvents} onChanged={() => refresh(site.id)} />
            </div>
          )}

          {tab === "site" && <SitePanel zones={zones} workers={workers} />}

          {tab === "tracking" && (
            <TrackingPanel siteId={site.id} workers={workers} zones={zones} dwellTime={dwellTime} onRefresh={() => refresh(site.id)} />
          )}

          {tab === "onboarding" && (
            <OnboardingPanel checklist={onboarding} calibrationLog={calibrationLog} onChanged={() => refresh(site.id)} siteId={site.id} />
          )}

          {tab === "emr" && <EmrPanel emr={emr} bonuses={bonuses} onChanged={() => refresh(site.id)} />}

          {tab === "billing" && <BillingPanel billing={billing} />}

          {tab === "audit" && (
            <div className="panel">
              <h2>Audit trail (compliance-grade, append-only, hash-chained)</h2>
              {user.role === "admin" && (
                <div style={{ marginBottom: 12 }}>
                  <button onClick={() => api.verifyAuditTrail().then(setAuditVerify)}>Verify chain integrity</button>
                  {auditVerify && (
                    <span style={{ marginLeft: 10, fontSize: 12 }} className={auditVerify.intact ? "badge low" : "badge critical"}>
                      {auditVerify.intact ? "Chain intact" : `Broken at ${auditVerify.broken_at_id}`}
                    </span>
                  )}
                </div>
              )}
              <AuditTrail entries={auditEntries} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
