from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class Profile(BaseModel):
    id: str
    name: str
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    timezone: str
    member_since: str
    coach_id: str
    tier: str


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


class Goal(BaseModel):
    id: str
    text: str
    priority: int
    target_date: str | None = None


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class Preferences(BaseModel):
    preferred_session_minutes: int
    training_days_per_week: int
    preferred_days: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Injury
# ---------------------------------------------------------------------------


class Injury(BaseModel):
    """
    Injury record as stored in member-context.json.

    This is the member-level stub that carries both the original thin fields
    (status, severity, since) and the Phase 5 extensions (onset_date,
    diagnosis, snomed_code, states).  Fields added in Phase 5 are optional
    so existing JSON files without them still validate.

    The API layer promotes this to the full app.models.injury.Injury when
    computing healing phases or building the conditional filter.
    """

    id: str
    region: str
    joint: str
    status: str
    severity: str
    since: str                          # ISO date string (original field)
    onset_date: str | None = None       # Phase 5: ISO date (preferred)
    diagnosis: str | None = None        # Phase 5: human-readable diagnosis
    notes: str | None = None
    snomedct_hint: str | None = None
    snomed_code: str | None = None      # Phase 5: SNOMED CT code
    # Phase 5: time series of daily check-in snapshots
    # Stored as raw dicts here; promoted to InjuryState in API layer
    states: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Workout history
# ---------------------------------------------------------------------------


class WorkoutSession(BaseModel):
    date: str
    title: str
    planned: bool
    completed: bool
    duration_min: int
    rpe: int | None = None
    exercises: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Adherence
# ---------------------------------------------------------------------------


class WeeklyCompletion(BaseModel):
    week_of: str
    pct: float


class Adherence(BaseModel):
    weekly_completion_pct: list[WeeklyCompletion] = Field(default_factory=list)
    trend: str


# ---------------------------------------------------------------------------
# Biomarkers
# ---------------------------------------------------------------------------


class WeightPoint(BaseModel):
    date: str
    kg: float


class Biomarkers(BaseModel):
    resting_hr_bpm: float
    hrv_ms: float
    sleep_hours_last_7_days: list[float] = Field(default_factory=list)
    weight_trend_kg: list[WeightPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Labs
# ---------------------------------------------------------------------------


class BloodPanel(BaseModel):
    date: str
    ldl_mg_dl: float | None = None
    hdl_mg_dl: float | None = None
    triglycerides_mg_dl: float | None = None
    hba1c_pct: float | None = None
    vitamin_d_ng_ml: float | None = None
    ferritin_ng_ml: float | None = None
    crp_mg_l: float | None = None


class DexaScan(BaseModel):
    date: str
    body_fat_pct: float | None = None
    lean_mass_kg: float | None = None
    fat_mass_kg: float | None = None
    bone_density_z_score: float | None = None
    visceral_fat_cm2: float | None = None


class Labs(BaseModel):
    blood_panel: BloodPanel | None = None
    dexa_scan: DexaScan | None = None


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------


class ChatAttachment(BaseModel):
    type: str
    caption: str | None = None


class ChatMessage(BaseModel):
    ts: str
    from_: str = Field(alias="from")
    text: str
    attachments: list[ChatAttachment] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Coach brief
# ---------------------------------------------------------------------------


class MorningTask(BaseModel):
    type: str
    text: str


class ChurnRisk(BaseModel):
    level: str
    reasons: list[str] = Field(default_factory=list)


class CoachBrief(BaseModel):
    generated_for: str
    morning_tasks: list[MorningTask] = Field(default_factory=list)
    churn_risk: ChurnRisk


# ---------------------------------------------------------------------------
# Top-level MemberContext
# ---------------------------------------------------------------------------


class MemberContext(BaseModel):
    """
    Full member context loaded from data/member-context.json.

    The JSON has 11 top-level keys (excluding the internal _note):
      profile, goals, preferences, equipment_available, injuries,
      workout_history, adherence, biomarkers, labs, chat_history, coach_brief
    """

    profile: Profile
    goals: list[Goal] = Field(default_factory=list)
    preferences: Preferences
    equipment_available: list[str] = Field(default_factory=list)
    injuries: list[Injury] = Field(default_factory=list)
    workout_history: list[WorkoutSession] = Field(default_factory=list)
    adherence: Adherence
    biomarkers: Biomarkers
    labs: Labs
    chat_history: list[ChatMessage] = Field(default_factory=list)
    coach_brief: CoachBrief
