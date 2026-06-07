"""
Deterministic workout assembler (the hybrid engine's structure step).

Builds a complete WorkoutPlan — selection, warmup/main/cooldown sectioning,
sets/reps/rest, ordering, sequencing roles, rule-templated per-exercise
rationale, and the stimulus distribution — over the ALREADY-SAFE candidate pool,
WITHOUT an LLM. A narrow LLM call (narrate.py) then writes only the four
session-level prose fields. This mirrors the assessment thesis: the graph/rules
make the decisions; the model only describes them.

Safety is unaffected: the input is the post-filter safe set, so nothing unsafe
can be selected here.
"""

from __future__ import annotations

import re

from app.models.exercise import Exercise
from app.models.injury import Injury
from app.models.plan import PlannedExercise, StimulusDistribution, WorkoutPlan
from app.generator.synthesize import _STIMULUS_WEIGHTS, _classify

# ---------------------------------------------------------------------------
# Training modes (rep/set/rest templates) inferred from the coach prompt
# ---------------------------------------------------------------------------

_MODES = {
    "strength": {"sets": 4, "reps": 5, "rest": 180},
    "power": {"sets": 5, "reps": 3, "rest": 180},
    "hypertrophy": {"sets": 4, "reps": 10, "rest": 75},
    "conditioning": {"sets": 3, "reps": 16, "rest": 40},
    "endurance": {"sets": 3, "reps": 18, "rest": 45},
    "mobility": {"sets": 2, "reps": None, "rest": 20},
}

_MODE_KEYWORDS = [
    ("power", ("power", "explosive", "explosiveness", "plyometric", "ballistic")),
    ("strength", ("strength", "max strength", "maximal", "heavy", "1rm", "strong")),
    ("conditioning", ("conditioning", "metcon", "hyrox", "circuit", "cardio", "metabolic", "hiit", "wod")),
    ("endurance", ("endurance", "stamina", "work capacity")),
    ("mobility", ("mobility", "recovery", "deload", "regen", "stretch", "flexibility")),
    ("hypertrophy", ("hypertrophy", "size", "muscle", "build", "bodybuilding")),
]

# Focus synonyms — expand the prompt into muscle/pattern tokens for relevance.
_FOCUS_SYNONYMS = {
    "lower": ["glute", "quad", "hamstring", "calf", "adductor", "lower", "squat", "hinge", "lunge"],
    "lower body": ["glute", "quad", "hamstring", "calf", "adductor", "lower", "squat", "hinge", "lunge"],
    "upper": ["chest", "shoulder", "back", "lat", "tricep", "bicep", "upper", "push", "pull", "press", "row"],
    "upper body": ["chest", "shoulder", "back", "lat", "tricep", "bicep", "upper", "push", "pull", "press", "row"],
    "push": ["push", "press", "chest", "shoulder", "tricep"],
    "pull": ["pull", "row", "back", "lat", "bicep"],
    "core": ["core", "oblique", "abs", "abdominal", "anti-rotation", "anti-extension"],
    "legs": ["glute", "quad", "hamstring", "calf", "squat", "hinge", "lunge"],
    "calisthenics": ["bodyweight", "push", "pull", "core", "calisthenic"],
}

_MOBILITY_HINTS = (
    "stretch", "mobility", "cars", "rotation", "circles", "foam", "cat-cow",
    "opener", "rolldown", "wall slide", "thread", "windmill",
)
# The dataset's `is_duration` flag is unreliable (most exercises are flagged
# True), so time-based work is inferred from the name/pattern instead.
_TIME_HINTS = (
    "hold", "plank", "stretch", "carry", "iso", "hang", "wall sit", "walkout",
    "dead hang", "bird dog", "copenhagen", "farmer", "suitcase",
)
_CONDITIONING_PATTERNS = ("cardio", "plyometric", "conditioning", "metabolic")
_COMPOUND_PATTERNS = ("squat", "hinge", "lunge", "push", "pull", "press", "row", "deadlift", "step-up", "carry")

# Cardio machines / locomotion are prescribed by calories, distance, or time —
# NEVER by reps ("16 reps on a SkiErg" is meaningless). Detection is by name
# (ergs, bikes, runners, sleds) and by the catalog's locomotion/cardio patterns.
_ERG_HINTS = (
    "erg", "skierg", "ski erg", "rower", "rowing", "concept2", "concept 2",
    "assault bike", "echo bike", "air bike", "fan bike", "elliptical",
)
_LOCOMOTION_HINTS = ("run", "sprint", "treadmill", "sled", "shuttle", "jog")
_STEADY_HINTS = ("zone 2", "zone-2", "zone2", "z2", "steady", "steady-state", "steady state")
# Target effort (% of max) for cardio intervals, keyed by inferred mode.
_MODE_INTENSITY = {
    "power": 90, "strength": 85, "conditioning": 85,
    "endurance": 75, "hypertrophy": 80, "mobility": None,
}
_ACTIVATION_MUSCLES = {"glutes", "core", "obliques", "rotator cuff", "hip flexors", "scapular"}

_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "of", "to", "in", "on",
    "today", "session", "workout", "avoid", "loaded", "do", "some", "more",
    "focus", "day", "good", "—", "-",
}


def _infer_mode(prompt: str) -> str:
    p = prompt.lower()
    for mode, kws in _MODE_KEYWORDS:
        if any(k in p for k in kws):
            return mode
    return "hypertrophy"


def _focus_tokens(prompt: str) -> set[str]:
    p = prompt.lower()
    tokens: set[str] = set()
    for phrase, syns in _FOCUS_SYNONYMS.items():
        if phrase in p:
            tokens.update(syns)
    for w in re.findall(r"[a-z]+", p):
        if len(w) > 2 and w not in _STOPWORDS:
            tokens.add(w)
    return tokens


def _is_time_based(ex: Exercise) -> bool:
    name = ex.name.lower()
    pats = " ".join(ex.movement_patterns).lower()
    return any(h in name for h in _TIME_HINTS) or "isometric" in pats


def _is_cardio_machine(ex: Exercise) -> bool:
    """True for ergs, bikes, runners, sleds — anything measured in cal/m/time."""
    name = ex.name.lower()
    pats = " ".join(ex.movement_patterns).lower()
    if any(h in name for h in _ERG_HINTS + _LOCOMOTION_HINTS):
        return True
    return "cardio" in pats or "locomotion" in pats


def _cardio_scheme(ex: Exercise, mode: str, sets: int, rest: int) -> dict:
    """Prescribe a cardio machine by calories / distance / time + intensity %.

    Ergs (row, ski, bike) → calories; locomotion (run, sled) → meters; generic
    cardio (jump rope, etc.) → seconds. Zone-2 / steady-state names collapse to
    one continuous block at a lower effort.
    """
    name = ex.name.lower()
    pats = " ".join(ex.movement_patterns).lower()
    base = {
        "sets": sets, "reps": None, "duration_seconds": None,
        "distance_meters": None, "calories": None, "rest_seconds": rest,
        "intensity_pct": _MODE_INTENSITY.get(mode, 80),
    }

    # Steady-state / Zone-2: one continuous block at conversational effort.
    if any(h in name for h in _STEADY_HINTS) or mode == "endurance":
        base.update(sets=1, duration_seconds=1200, rest_seconds=0, intensity_pct=65)
        return base

    if any(h in name for h in _ERG_HINTS):
        base["calories"] = 12                      # ~12 cal intervals
    elif any(h in name for h in _LOCOMOTION_HINTS) or "locomotion" in pats:
        base["distance_meters"] = 200              # 200 m intervals
    else:
        base["duration_seconds"] = 40              # generic cardio → time
    return base


def _ex_text(ex: Exercise) -> str:
    return " ".join(
        [ex.name] + list(ex.muscle_groups) + list(ex.movement_patterns)
    ).lower()


def _relevance(ex: Exercise, focus: set[str]) -> int:
    text = _ex_text(ex)
    return sum(1 for t in focus if t in text)


def _role(ex: Exercise) -> str:
    name = ex.name.lower()
    pats = [p.lower() for p in ex.movement_patterns]
    muscles = [m.lower() for m in ex.muscle_groups]
    if any(h in name for h in _MOBILITY_HINTS) or any(
        "mobility" in p or "stretch" in p for p in pats
    ):
        return "mobility"
    if any(any(c in p for c in _CONDITIONING_PATTERNS) for p in pats):
        return "conditioning"
    primary = set(muscles[:1])
    if len(muscles) <= 2 and (primary & _ACTIVATION_MUSCLES):
        return "activation"
    if len(muscles) >= 2 and any(k in p for p in pats for k in _COMPOUND_PATTERNS):
        return "compound"
    return "accessory"


def _scheme(mode: str, role: str, ex: Exercise, load_tolerance_pct: float) -> dict:
    """Sets / reps / duration / rest for an exercise given the mode + role."""
    base = _MODES[mode]
    sets = base["sets"]
    reps = base["reps"]
    rest = base["rest"]

    if role == "activation":
        sets, reps, rest = 2, 12, 30
    elif role == "mobility":
        sets, reps, rest = 1, None, 15
    elif role == "conditioning":
        sets, reps, rest = 3, 16, 35
    elif role == "accessory" and mode in ("strength", "power"):
        # accessories in a strength day are hypertrophy-range
        sets, reps, rest = 3, 10, 75

    # Load-tolerance cap: trim a set and ease rest when the member is limited.
    if load_tolerance_pct < 0.7 and sets > 2:
        sets -= 1

    # Cardio machines / locomotion: calories / distance / time + intensity %.
    if _is_cardio_machine(ex):
        return _cardio_scheme(ex, mode, sets, rest)

    # Other duration-based work (holds, carries, planks) → time, no intensity %.
    if _is_time_based(ex) or reps is None:
        return {
            "sets": sets, "reps": None, "duration_seconds": 40,
            "distance_meters": None, "calories": None,
            "rest_seconds": rest, "intensity_pct": None,
        }

    # Resistance work: reps as before (load is governed by the load cap).
    return {
        "sets": sets, "reps": reps, "duration_seconds": None,
        "distance_meters": None, "calories": None,
        "rest_seconds": rest, "intensity_pct": None,
    }


def _primary_muscle(ex: Exercise) -> str:
    return ex.muscle_groups[0] if ex.muscle_groups else "the target muscles"


def _rationale(ex: Exercise, role: str) -> str:
    m = _primary_muscle(ex)
    return {
        "activation": f"Activation for the {m} to stabilize before loaded work.",
        "primer": f"Primes the {m} ahead of the main movement.",
        "compound": f"Primary compound — the session's main {m} driver.",
        "accessory": f"Accessory volume to build the {m}.",
        "conditioning": "Metabolic finisher for work capacity.",
        "cooldown": f"Down-regulates and lengthens the {m}.",
    }.get(role, f"Targets the {m}.")


def _sequencing_rationale(role: str, first: bool, last: bool) -> str:
    return {
        "activation": "Early in the warmup to wake up stabilizers before load.",
        "primer": "Placed just before the compound it protects.",
        "compound": "CNS-intensive compound first, while you're freshest.",
        "accessory": "Follows the compounds to add volume without pre-fatigue.",
        "conditioning": "Placed last so it doesn't pre-fatigue the prime movers.",
        "cooldown": "Final — parasympathetic down-regulation to close the session.",
    }.get(role, "Sequenced by training priority.")


def _make_pe(ex: Exercise, order: int, role: str, scheme: dict, first: bool, last: bool) -> PlannedExercise:
    return PlannedExercise(
        exercise_id=ex.id,
        name=ex.name,
        order=order,
        sets=scheme["sets"],
        reps=scheme["reps"],
        duration_seconds=scheme["duration_seconds"],
        distance_meters=scheme.get("distance_meters"),
        calories=scheme.get("calories"),
        rest_seconds=scheme["rest_seconds"],
        intensity_pct=scheme.get("intensity_pct"),
        rationale=_rationale(ex, role),
        sequencing_rationale=_sequencing_rationale(role, first, last),
        sequencing_role=role if role in (
            "activation", "primer", "compound", "accessory", "conditioning", "cooldown"
        ) else "accessory",
    )


def assemble_plan(
    safe_exercises: list[Exercise],
    prompt: str,
    time_minutes: int,
    load_tolerance_pct: float,
    injury: Injury | None,
) -> WorkoutPlan:
    """Deterministically assemble a WorkoutPlan from the safe pool."""
    mode = _infer_mode(prompt)
    focus = _focus_tokens(prompt)

    # Bucket the safe pool by role and rank by (relevance desc, priority_tier asc)
    buckets: dict[str, list[Exercise]] = {
        "mobility": [], "activation": [], "compound": [], "accessory": [], "conditioning": []
    }
    for ex in safe_exercises:
        buckets.setdefault(_role(ex), []).append(ex)
    for role in buckets:
        buckets[role].sort(key=lambda e: (-_relevance(e, focus), getattr(e, "priority_tier", 2)))

    # Section sizes scale with the time window.
    main_n = 4 if time_minutes < 40 else 6 if time_minutes >= 70 else 5
    if mode == "mobility":
        main_n = 0

    used: set[str] = set()

    def take(pool: list[Exercise], n: int) -> list[Exercise]:
        out = []
        for ex in pool:
            if ex.id in used:
                continue
            used.add(ex.id)
            out.append(ex)
            if len(out) >= n:
                break
        return out

    # Warmup: activation + mobility primers (2-3)
    warm_pool = buckets["activation"] + buckets["mobility"]
    warm = take(warm_pool, 3 if time_minutes >= 45 else 2)

    # Main: compounds first, then accessory, then conditioning (for metcon modes)
    if mode in ("conditioning", "endurance"):
        main_src = buckets["conditioning"] + buckets["compound"] + buckets["accessory"]
    elif mode == "mobility":
        main_src = []
    else:
        main_src = buckets["compound"] + buckets["accessory"]
    main = take(main_src, main_n)

    # Cooldown: a stretch/mobility not used yet (1-2)
    cool = take(buckets["mobility"], 2 if mode == "mobility" else 1)

    # Build PlannedExercise lists with schemes + roles
    warmup_pe: list[PlannedExercise] = []
    for i, ex in enumerate(warm):
        role = _role(ex)
        role = "activation" if role == "activation" else "primer"
        warmup_pe.append(_make_pe(ex, i + 1, role, _scheme(mode, "activation", ex, load_tolerance_pct), i == 0, i == len(warm) - 1))

    main_pe: list[PlannedExercise] = []
    for i, ex in enumerate(main):
        role = _role(ex)
        main_pe.append(_make_pe(ex, i + 1, role, _scheme(mode, role, ex, load_tolerance_pct), i == 0, i == len(main) - 1))

    cooldown_pe: list[PlannedExercise] = []
    for i, ex in enumerate(cool):
        cooldown_pe.append(_make_pe(ex, i + 1, "cooldown", _scheme(mode, "mobility", ex, load_tolerance_pct), i == 0, i == len(cool) - 1))

    dist = _compute_distribution(warmup_pe + main_pe + cooldown_pe, warm + main + cool)

    return WorkoutPlan(
        warmup=warmup_pe,
        main=main_pe,
        cooldown=cooldown_pe,
        total_minutes=time_minutes,
        stimulus_distribution=dist,
        # Session-level prose is filled by the narrate step (or a templated fallback).
        stimulus="",
        target_adaptation="",
        design_rationale="",
        sequence_logic="",
    )


def _compute_distribution(planned: list[PlannedExercise], exercises: list[Exercise]) -> StimulusDistribution:
    """Reuse the synthesize classifier to read the assembled plan's stimulus mix."""
    by_id = {e.id: e for e in exercises}
    gauges = {"strength": 0.0, "conditioning": 0.0, "mobility": 0.0}
    total = 0.0
    # crude section inference: warmup/cooldown handled by role
    for pe in planned:
        ex = by_id.get(pe.exercise_id)
        is_dur = (_is_time_based(ex) or _is_cardio_machine(ex)) if ex else (pe.reps is None)
        patterns = ex.movement_patterns if ex else []
        section = "cooldown" if pe.sequencing_role == "cooldown" else (
            "warmup" if pe.sequencing_role in ("activation", "primer") else "main"
        )
        adapt = _classify(pe.reps, pe.rest_seconds, is_dur, pe.name, patterns, section)
        w = float(pe.sets or 3)
        total += w
        ws, wc, wm = _STIMULUS_WEIGHTS[adapt]
        gauges["strength"] += ws * w
        gauges["conditioning"] += wc * w
        gauges["mobility"] += wm * w
    total = total or 1.0
    return StimulusDistribution(
        strength=round(100 * gauges["strength"] / total),
        conditioning=round(100 * gauges["conditioning"] / total),
        mobility=round(100 * gauges["mobility"] / total),
    )
