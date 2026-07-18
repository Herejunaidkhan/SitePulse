// In production both services share one domain (Vercel rewrites /api/* to the backend
// service), so BASE is relative. Locally, .env.local points VITE_API_URL at the standalone dev backend.
const BASE = `${import.meta.env.VITE_API_URL ?? ""}/api`;

let authToken: string | null = localStorage.getItem("sitepulse_token");

export function setToken(token: string | null) {
  authToken = token;
  if (token) localStorage.setItem("sitepulse_token", token);
  else localStorage.removeItem("sitepulse_token");
}

export function getToken() {
  return authToken;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let message = `${path} -> ${res.status}`;
    try {
      const detail = (await res.json()).detail;
      if (typeof detail === "string") message = detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});

export interface User {
  id: string;
  org_id: string;
  site_id: string | null;
  email: string;
  name: string;
  role: "admin" | "safety_officer" | "foreman" | "worker";
}

export interface Site {
  id: string;
  org_id: string;
  name: string;
  address: string;
  status: string;
}

export interface Zone {
  id: string;
  site_id: string;
  name: string;
  zone_type: string;
  risk_category: "low" | "medium" | "high" | "critical";
}

export interface Worker {
  id: string;
  site_id: string;
  name: string;
  trade: string;
  badge_id: string;
  active: boolean;
}

export interface Detection {
  id: string;
  site_id: string;
  detection_type: string;
  confidence_score: number;
  worker_id: string | null;
  zone_id: string | null;
  equipment_id: string | null;
  timestamp: string;
  model_version: string;
  risk_event_id: string | null;
}

export interface RiskEvent {
  id: string;
  site_id: string;
  zone_id: string | null;
  risk_score: number;
  risk_category: "low" | "medium" | "high" | "critical";
  explanation: string;
  status: "open" | "acknowledged" | "intervention_logged" | "resolved" | "false_positive";
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  intervention_notes: string | null;
}

export interface Alert {
  id: string;
  risk_event_id: string;
  channel: string;
  recipient_user_id: string | null;
  sent_at: string;
  acknowledged_at: string | null;
  response_time_seconds: number | null;
}

export interface IncidentLogEntry {
  id: string;
  site_id: string;
  risk_event_id: string | null;
  type: string;
  description: string;
  severity: string;
  injury_flag: boolean;
  created_at: string;
}

export interface AuditTrailEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  timestamp: string;
}

export interface ZoneHeat {
  zone_id: string;
  zone_name: string;
  avg_risk_score: number;
  open_count: number;
}

export interface DashboardSummary {
  open_risk_events: number;
  critical_open: number;
  high_open: number;
  alerts_pending_ack: number;
  zone_heat: ZoneHeat[];
  mean_time_to_ack_seconds: number | null;
}

export interface OshaPattern {
  id: string;
  pattern_name: string;
  description: string;
  correlated_detection_types: string;
  base_severity_weight: number;
  source_citation: string;
}

export interface IotSensor {
  id: string;
  site_id: string;
  type: string;
  equipment_id: string | null;
  worker_id: string | null;
  last_reading_at: string | null;
  battery_level: number;
  status: string;
}

export interface DwellTimeEntry {
  zone_id: string;
  zone_name: string;
  ping_count: number;
}

export interface LocationPing {
  id: string;
  worker_id: string;
  site_id: string;
  zone_id: string | null;
  timestamp: string;
  source: string;
}

export interface BillingSummary {
  plan_name: string;
  base_fee: number;
  camera_count: number;
  camera_unit_price: number;
  sensor_count: number;
  sensor_unit_price: number;
  estimated_total: number;
}

export interface IncidentBonus {
  id: string;
  org_id: string;
  risk_event_id: string;
  estimated_severity_avoided: string;
  bonus_amount: number;
  verification_status: "pending" | "verified" | "disputed" | "rejected";
  created_at: string;
}

export interface EmrSummary {
  period: string;
  org_id: string;
  incidents_prevented_count: number;
  estimated_bonus_total: number;
  resolved_risk_events: number;
  open_high_critical_risk_events: number;
  exposure_hours: number;
  computed_emr_delta: number;
}

export interface CalibrationLogEntry {
  id: string;
  site_id: string;
  threshold_type: string;
  old_value: string;
  new_value: string;
  changed_by: string | null;
  changed_at: string;
  justification: string;
}

export interface OnboardingChecklist {
  stage: string;
  site_status: string;
  camera_count: number;
  zone_count: number;
  ppe_requirement_count: number;
  calibration_entries: number;
  users_assigned: number;
  ready_for_next_stage: boolean;
}

export interface AuditVerifyResult {
  intact: boolean;
  broken_at_id: string | null;
}

export const api = {
  login: (email: string, password: string) =>
    post<{ token: string; user: User }>("/auth/login", { email, password }),
  me: () => get<User>("/auth/me"),

  sites: () => get<Site[]>("/sites"),
  zones: (siteId: string) => get<Zone[]>(`/sites/${siteId}/zones`),
  workers: (siteId: string) => get<Worker[]>(`/sites/${siteId}/workers`),

  simulateDetection: (siteId: string, payload: { detection_type?: string; zone_id?: string; worker_id?: string; confidence_score?: number }) =>
    post<{ detection: Detection; risk_event: RiskEvent; alerts_created: number }>(`/sites/${siteId}/detections/simulate`, payload),
  detections: (siteId: string) => get<Detection[]>(`/sites/${siteId}/detections`),

  riskEvents: (siteId: string, status?: string) =>
    get<RiskEvent[]>(`/sites/${siteId}/risk-events${status ? `?status=${status}` : ""}`),
  acknowledgeRiskEvent: (id: string) => post<RiskEvent>(`/risk-events/${id}/acknowledge`),
  logIntervention: (id: string, description: string) =>
    post<RiskEvent>(`/risk-events/${id}/log-intervention`, { description }),
  resolveRiskEvent: (id: string, status: "resolved" | "false_positive") =>
    post<RiskEvent>(`/risk-events/${id}/resolve`, { status }),

  alerts: (siteId: string, unacknowledgedOnly = false) =>
    get<Alert[]>(`/sites/${siteId}/alerts${unacknowledgedOnly ? "?unacknowledged_only=true" : ""}`),

  incidents: (siteId: string) => get<IncidentLogEntry[]>(`/sites/${siteId}/incidents`),
  createIncident: (siteId: string, payload: { type: string; description: string; severity: string; injury_flag: boolean }) =>
    post<IncidentLogEntry>(`/sites/${siteId}/incidents`, payload),

  auditTrail: (siteId: string) => get<AuditTrailEntry[]>(`/sites/${siteId}/audit-trail`),
  verifyAuditTrail: () => get<AuditVerifyResult>("/audit-trail/verify"),
  oshaPatterns: () => get<OshaPattern[]>("/osha-patterns"),
  dashboardSummary: (siteId: string) => get<DashboardSummary>(`/sites/${siteId}/dashboard-summary`),

  simulateSensorReading: (siteId: string, payload: { sensor_type: string; equipment_id?: string; worker_id?: string; value?: Record<string, number> }) =>
    post<{ id: string }>(`/sites/${siteId}/iot-sensors/simulate-reading`, payload),
  iotSensors: (siteId: string) => get<IotSensor[]>(`/sites/${siteId}/iot-sensors`),

  simulateLocationPing: (siteId: string, workerId: string, zoneId?: string) =>
    post<LocationPing>(`/sites/${siteId}/location/simulate-ping`, { worker_id: workerId, zone_id: zoneId }),
  dwellTime: (siteId: string) => get<DwellTimeEntry[]>(`/sites/${siteId}/location/dwell-time`),

  billingSummary: () => get<BillingSummary>("/billing/summary"),

  incidentBonuses: (orgId: string, status?: string) =>
    get<IncidentBonus[]>(`/orgs/${orgId}/incident-bonuses${status ? `?status=${status}` : ""}`),
  verifyBonus: (bonusId: string, status: "verified" | "disputed" | "rejected") =>
    post<IncidentBonus>(`/incident-bonuses/${bonusId}/verify`, { status }),
  emrSummary: (orgId: string) => get<EmrSummary>(`/orgs/${orgId}/emr-summary`),

  calibrationLog: (siteId: string) => get<CalibrationLogEntry[]>(`/sites/${siteId}/calibration-log`),
  createCalibrationEntry: (siteId: string, payload: { threshold_type: string; old_value: string; new_value: string; justification: string }) =>
    post<CalibrationLogEntry>(`/sites/${siteId}/calibration-log`, payload),

  onboardingChecklist: (siteId: string) => get<OnboardingChecklist>(`/sites/${siteId}/onboarding-checklist`),
  advanceOnboarding: (siteId: string, stage: string, notes = "") =>
    post<OnboardingChecklist>(`/sites/${siteId}/onboarding/advance`, { stage, notes }),
};
