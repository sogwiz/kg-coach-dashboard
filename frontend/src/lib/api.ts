/**
 * Typed fetch wrappers for the KG Coach Dashboard backend API.
 *
 * All requests go through the Vite proxy at /api → localhost:8000.
 * The auth token (if present) is read from localStorage and sent as
 * an Authorization: Bearer header on every request.
 */

// ---------------------------------------------------------------------------
// Shared types (mirrors backend Pydantic models)
// ---------------------------------------------------------------------------

export interface CoachProfile {
  coach_id: string;
  name: string;
  email: string;
  role: string;
  avatar_initials: string;
}

export interface LoginResponse {
  token: string;
  coach: CoachProfile;
}

export interface MemberSummary {
  member_id: string;
  name: string;
  age: number;
  sex: string;
  churn_risk_level: string;
  adherence_trend: string;
  active_injury: string | null;
}

export interface MorningTask {
  type: string;
  text: string;
}

export interface ChurnRisk {
  level: string;
  reasons: string[];
}

export interface CoachBrief {
  generated_for: string;
  morning_tasks: MorningTask[];
  churn_risk: ChurnRisk;
}

export interface WeeklyCompletion {
  week_of: string;
  pct: number;
}

export interface Adherence {
  weekly_completion_pct: WeeklyCompletion[];
  trend: string;
}

export interface Injury {
  id: string;
  region: string;
  joint: string;
  status: string;
  severity: string;
  since: string;
  onset_date: string | null;
  diagnosis: string | null;
  notes: string | null;
  snomed_code: string | null;
  states: InjuryState[];
}

export interface InjuryState {
  injury_id: string;
  recorded_at: string;
  inflammation: "none" | "mild" | "moderate" | "severe";
  pain_on: MovementType[];
  subjective_pain: number;
  load_tolerance_pct: number;
  notes: string | null;
}

export type MovementType = "flexion" | "extension" | "rotation" | "load" | "impact";

export interface InjuryStateCreate {
  inflammation: "none" | "mild" | "moderate" | "severe";
  pain_on: MovementType[];
  subjective_pain: number;
  load_tolerance_pct: number;
  notes?: string;
}

export interface MemberContext {
  profile: {
    id: string;
    name: string;
    age: number;
    sex: string;
    height_cm: number;
    weight_kg: number;
    timezone: string;
    member_since: string;
    coach_id: string;
    tier: string;
  };
  goals: Array<{ id: string; text: string; priority: number; target_date: string | null }>;
  preferences: {
    preferred_session_minutes: number;
    training_days_per_week: number;
    preferred_days: string[];
    dislikes: string[];
    notes: string | null;
  };
  equipment_available: string[];
  injuries: Injury[];
  adherence: Adherence;
  biomarkers: {
    resting_hr_bpm: number;
    hrv_ms: number;
    sleep_hours_last_7_days: number[];
    weight_trend_kg: Array<{ date: string; kg: number }>;
  };
  coach_brief: CoachBrief;
}

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

const TOKEN_KEY = "kg_coach_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchMe(): Promise<CoachProfile> {
  return apiFetch<CoachProfile>("/api/auth/me");
}

// ---------------------------------------------------------------------------
// Members endpoints
// ---------------------------------------------------------------------------

export async function fetchMembers(): Promise<MemberSummary[]> {
  return apiFetch<MemberSummary[]>("/api/members");
}

export async function fetchMember(memberId: string): Promise<MemberContext> {
  return apiFetch<MemberContext>(`/api/members/${memberId}`);
}

// ---------------------------------------------------------------------------
// Injury endpoints
// ---------------------------------------------------------------------------

export async function fetchInjuryHistory(
  memberId: string,
  injuryId: string,
  days = 14
): Promise<InjuryState[]> {
  return apiFetch<InjuryState[]>(
    `/api/members/${memberId}/injuries/${injuryId}/history?days=${days}`
  );
}

export async function postInjuryCheckIn(
  memberId: string,
  injuryId: string,
  state: InjuryStateCreate
): Promise<InjuryState> {
  return apiFetch<InjuryState>(
    `/api/members/${memberId}/injuries/${injuryId}/check-in`,
    {
      method: "POST",
      body: JSON.stringify(state),
    }
  );
}
