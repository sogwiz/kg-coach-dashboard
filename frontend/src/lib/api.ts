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
  workout_sent_today: boolean;
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
// Generator types (mirrors backend generator route _serialise_output shape)
// ---------------------------------------------------------------------------

export type SequencingRole =
  | "activation"
  | "primer"
  | "compound"
  | "accessory"
  | "conditioning"
  | "cooldown";

export interface PlannedExercise {
  exercise_id: string;
  name: string;
  order: number;
  sets: number;
  reps: number | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  calories: number | null;
  rest_seconds: number;
  intensity_pct: number | null;
  rationale: string;
  sequencing_rationale: string;
  sequencing_role: SequencingRole;
}

export interface StimulusDistribution {
  strength: number; // 0-100
  conditioning: number; // 0-100
  mobility: number; // 0-100
}

export interface WorkoutPlan {
  warmup: PlannedExercise[];
  main: PlannedExercise[];
  cooldown: PlannedExercise[];
  total_minutes: number;
  stimulus_distribution?: StimulusDistribution;
  stimulus: string;
  target_adaptation: string;
  design_rationale: string;
  sequence_logic: string;
}

export interface VariantProvenance {
  generated_at: string;
  prompt: string;
  time_window_minutes: number;
  healing_phase: string | null;
  load_tolerance_pct: number;
  stale_check_in: boolean;
  exercises_filtered_out: Array<{ name: string; id: string; reason: string }>;
  equipment_available: string[];
  injury_state_used: InjuryState | null;
}

export interface WorkoutVariant {
  variant_id: string;   // "strength" | "conditioning" | "mobility"
  label: string;
  optimizes_for: string;
  plan: WorkoutPlan;
  provenance: VariantProvenance;
}

export interface TraceSummary {
  safe_count: number;
  removed_count: number;
  substitution_count: number;
  load_tolerance_pct: number;
  stale_check_in: boolean;
  removed: Array<{ id: string; name: string; reason: string }>;
}

export interface DecisionStep {
  name: string;
  detail: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  kind: "deterministic" | "llm";
  duration_ms?: number | null;
}

export interface GeneratorOutput {
  variants: WorkoutVariant[];
  trace_summary: TraceSummary;
  selected_variant_id: string | null;
  decision_trace: DecisionStep[];
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

// ---------------------------------------------------------------------------
// Generator endpoints
// ---------------------------------------------------------------------------

export async function postGenerate(
  prompt: string,
  timeWindowMinutes: number,
  memberId: string
): Promise<GeneratorOutput> {
  return apiFetch<GeneratorOutput>("/api/generate", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      time_window_minutes: timeWindowMinutes,
      member_id: memberId,
    }),
  });
}

export async function postGenerateSelect(
  memberId: string,
  variantId: string
): Promise<GeneratorOutput> {
  return apiFetch<GeneratorOutput>("/api/generate/select", {
    method: "POST",
    body: JSON.stringify({ member_id: memberId, variant_id: variantId }),
  });
}

/**
 * Regenerate the member's current plan as a fresh, distinct variation. The
 * backend feeds the previous session to the LLM so the result differs while
 * honoring the same prompt + time window. Optional `adjustment` applies a tweak
 * (e.g. "more posterior chain", "no barbell").
 */
export async function postRegenerate(
  memberId: string,
  adjustment?: string
): Promise<GeneratorOutput> {
  return apiFetch<GeneratorOutput>("/api/generate/regenerate", {
    method: "POST",
    body: JSON.stringify({
      member_id: memberId,
      adjustment: adjustment || undefined,
    }),
  });
}

export interface GenStatusEvent {
  stage: "resolve" | "safety" | "structuring";
  safe_count?: number;
  removed_count?: number;
  filter_ms?: number;
  engine?: "hybrid" | "llm";
}

/**
 * Streaming generate — POST /api/generate/stream returns newline-delimited JSON
 * events. `onEvent` fires per event ({type:"status"|"complete"|"error", ...}).
 */
export async function streamGenerate(
  prompt: string,
  minutes: number,
  memberId: string,
  onEvent: (ev: Record<string, unknown>) => void,
  engine: "hybrid" | "llm" = "hybrid"
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch("/api/generate/stream", {
    method: "POST",
    headers,
    body: JSON.stringify({
      prompt,
      time_window_minutes: minutes,
      member_id: memberId,
      engine,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += value;
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) {
        try {
          onEvent(JSON.parse(line));
        } catch {
          /* ignore malformed line */
        }
      }
    }
  }
  const tail = buf.trim();
  if (tail) {
    try {
      onEvent(JSON.parse(tail));
    } catch {
      /* ignore */
    }
  }
}

// ---------------------------------------------------------------------------
// Send workout types + endpoint
// ---------------------------------------------------------------------------

export interface SendWorkoutRequest {
  member_id: string;
  variant_id: string;
  message?: string;
}

export interface SendWorkoutResponse {
  success: boolean;
  member_id: string;
  variant_id: string;
  message: string;
  sent_at: string;
}

export interface SendStatusResponse {
  member_id: string;
  sent_today: boolean;
  last_sent: string | null;
  last_message: string | null;
}

export async function postSendWorkout(
  memberId: string,
  variantId: string,
  message?: string
): Promise<SendWorkoutResponse> {
  return apiFetch<SendWorkoutResponse>("/api/generate/send", {
    method: "POST",
    body: JSON.stringify({
      member_id: memberId,
      variant_id: variantId,
      message: message || undefined,
    }),
  });
}

export async function fetchSendStatus(memberId: string): Promise<SendStatusResponse> {
  return apiFetch<SendStatusResponse>(`/api/generate/send-status/${memberId}`);
}

export async function fetchPreviewMessage(
  memberId: string,
  variantId: string
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/api/generate/preview-message?member_id=${memberId}&variant_id=${variantId}`);
}

// ---------------------------------------------------------------------------
// Graph types (mirrors backend GraphPayload)
// ---------------------------------------------------------------------------

export interface ExclusionAttribution {
  injury: string;       // "left knee — patellofemoral pain syndrome"
  joint: string;        // injured joint slug
  reason: string;       // filter reason string
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;         // exercise / muscle / joint / pattern / equipment / injury_concept
  filtered_out: boolean;
  on_filter_path: boolean;
  excluded_by?: ExclusionAttribution[];
}

export interface MemberInjury {
  joint: string;
  region: string;
  diagnosis: string;
  label: string;        // display label
  healing_phase?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;     // stresses / targets / requires / part-of / contraindicated-for
  on_filter_path: boolean;
  movement_types: string[];
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  member_id: string | null;
  member_injuries?: MemberInjury[];
  filtered_exercise_ids: string[];
  filter_path_node_ids: string[];
}

// ---------------------------------------------------------------------------
// Copilot / chat types
// ---------------------------------------------------------------------------

export interface ChatAttachment {
  type: string;
  url?: string | null;
  caption?: string | null;
}

export interface ChatMessage {
  ts: string;
  from: string;          // "member" | "coach" | "system"
  text: string;
  attachments: ChatAttachment[];
  // client-side extra fields for rendering
  role?: "user" | "assistant" | "event";
  isStreaming?: boolean;
  // For role === "event": logged activity (e.g. a generated workout) rendered
  // as a clickable chip in the conversation.
  event?: { kind: string; prompt?: string; minutes?: number };
}

// ---------------------------------------------------------------------------
// Graph endpoint
// ---------------------------------------------------------------------------

export async function fetchGraph(memberId?: string | null): Promise<GraphPayload> {
  const url = memberId
    ? `/api/graph?member_id=${encodeURIComponent(memberId)}`
    : "/api/graph";
  return apiFetch<GraphPayload>(url);
}

// ---------------------------------------------------------------------------
// Exercises types + endpoint (Phase 13 — Creative Canvas)
// ---------------------------------------------------------------------------

/**
 * Mirrors backend ExerciseItem (exercises.py).
 * Fields: id, name, movement_patterns, muscle_groups, equipment_required,
 *         joints_loaded, priority_tier, contraindicated
 */
export interface ExerciseItem {
  id: string;
  name: string;
  movement_patterns: string[];
  muscle_groups: string[];
  equipment_required: string[];
  joints_loaded: string[];
  priority_tier: number;
  contraindicated: boolean;
}

export interface ExerciseListResponse {
  exercises: ExerciseItem[];
  total: number;
  member_id: string | null;
}

export async function fetchExercises(params?: {
  search?: string;
  memberId?: string;
}): Promise<ExerciseListResponse> {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.memberId) qs.set("member_id", params.memberId);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<ExerciseListResponse>(`/api/exercises${query}`);
}

// ---------------------------------------------------------------------------
// Canvas synthesis (analyze a coach-built workout)
// ---------------------------------------------------------------------------

export interface CanvasAnalyzeItem {
  exercise_id: string;
  name: string;
  section: string;
  sets_reps: string;
  rest: string;
  intensity: string;
}

export interface CanvasAnalysis {
  total_exercises: number;
  total_sets: number;
  per_section: { warmup: number; main: number; cooldown: number };
  rep_histogram: Record<string, number>;
  adaptation_scores: Record<string, number>;
  primary_adaptation: string;
  primary_label: string;
  stimulus_distribution: StimulusDistribution;
  verdict: string;
  tip: string;
}

export async function analyzeCanvas(items: CanvasAnalyzeItem[]): Promise<CanvasAnalysis> {
  return apiFetch<CanvasAnalysis>("/api/canvas/analyze", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

// ---------------------------------------------------------------------------
// Copilot endpoints
// ---------------------------------------------------------------------------

export async function fetchChatHistory(memberId: string): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`/api/copilot/members/${memberId}/chat-history`);
}

/**
 * Send a message to the copilot (sync endpoint for simplicity).
 * Falls back to /chat/sync which returns JSON {response: string}.
 */
export async function postCopilotSync(
  memberId: string,
  message: string,
  attachments: ChatAttachment[] = []
): Promise<{ response: string; member_id: string }> {
  return apiFetch<{ response: string; member_id: string }>("/api/copilot/chat/sync", {
    method: "POST",
    body: JSON.stringify({ member_id: memberId, message, attachments }),
  });
}

/**
 * Stream a copilot response via the streaming endpoint.
 * Returns a ReadableStream<string>. The caller handles chunks.
 * Throws on non-200 responses.
 */
export async function streamCopilot(
  memberId: string,
  message: string,
  attachments: ChatAttachment[] = [],
  context?: string
): Promise<ReadableStreamDefaultReader<string>> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch("/api/copilot/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({
      member_id: memberId,
      message,
      attachments,
      context: context || undefined,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  return reader;
}
