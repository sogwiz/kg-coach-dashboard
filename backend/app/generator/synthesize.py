"""
Workout synthesis — deterministic analysis of a coach-built Creative Canvas.

The reverse of the generator: given the exercises + sets/reps/rest schemes a
coach composed, classify the ACTUAL training adaptations and stimulus so the
coach can compare *intended vs actual* — e.g. "I built a strength session, but
the rep ranges read as hypertrophy / strength-endurance."

No LLM: this is exercise-science rules over the schemes (the strength–endurance
continuum), so it is instant and fully reproducible.
"""

from __future__ import annotations

import re

# Adaptation buckets along the strength → endurance continuum (+ power, mobility)
ADAPTATIONS = [
    "max_strength",
    "power",
    "hypertrophy",
    "strength_endurance",
    "conditioning",
    "mobility",
]

ADAPTATION_LABEL = {
    "max_strength": "Maximal strength",
    "power": "Power / explosiveness",
    "hypertrophy": "Hypertrophy (size)",
    "strength_endurance": "Strength-endurance",
    "conditioning": "Conditioning / metabolic",
    "mobility": "Mobility / recovery",
}

_POWER_HINTS = (
    "slam", "throw", "toss", "jump", "clean", "snatch", "jerk", "broad",
    "plyo", "explosive", "sprint", "skater", "bound", "hop",
)
_CONDITIONING_PATTERNS = ("cardio", "plyometric", "conditioning", "metabolic")
_MOBILITY_HINTS = (
    "stretch", "mobility", "cars", "rotation", "circles", "foam", "cat-cow",
    "opener", "rolldown", "walkout", "wall slide", "thread", "windmill",
)

# How each adaptation contributes to the three stimulus gauges (independent 0-100).
_STIMULUS_WEIGHTS = {
    # adaptation: (strength, conditioning, mobility)
    "max_strength": (1.0, 0.05, 0.0),
    "power": (0.85, 0.30, 0.0),
    "hypertrophy": (0.75, 0.25, 0.05),
    "strength_endurance": (0.40, 0.65, 0.10),
    "conditioning": (0.15, 1.0, 0.05),
    "mobility": (0.0, 0.10, 1.0),
}

# Templated verdict + an intended-vs-actual nudge per primary adaptation.
_VERDICT = {
    "max_strength": (
        "Built for maximal strength — low reps (1-5), heavy load, long rest, "
        "training top-end force.",
        "To add muscle size, fold in some 6-12 rep accessory work between the "
        "heavy compounds.",
    ),
    "hypertrophy": (
        "This reads as hypertrophy (muscle size): most working sets sit in the "
        "6-12 rep range with moderate rest.",
        "If you intended maximal strength, drop the main compounds to 3-5 reps "
        "and extend rest to 3-5 minutes.",
    ),
    "strength_endurance": (
        "This trains strength-endurance — higher reps (13-20) and shorter rest "
        "build muscular endurance more than peak strength.",
        "For maximal strength, cut reps to 3-5 and load heavier; for "
        "hypertrophy, target 6-12 reps.",
    ),
    "power": (
        "Built for power / explosiveness — fast, low-rep movements that train "
        "rate of force development.",
        "Pair with heavy 1-5 rep strength work for the best power transfer.",
    ),
    "conditioning": (
        "This is conditioning / metabolic work — high reps, short rest, and "
        "duration efforts biased toward work capacity.",
        "For a strength stimulus, lower the reps (3-8), add load, and lengthen "
        "rest periods.",
    ),
    "mobility": (
        "Mostly mobility and recovery — low systemic load, ROM-focused.",
        "Add loaded compound work in the main block if you want a strength or "
        "hypertrophy stimulus.",
    ),
}


def _parse_sets_reps(text: str) -> tuple[int | None, float | None]:
    """Parse '(sets, reps)' from free text: '3 x 10', '5x5', '3 sets of 8', '12 reps'."""
    s = (text or "").lower()
    m = re.search(r"(\d+)\s*[x×]\s*(\d+)", s)
    if m:
        return int(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*sets?\s*(?:of|x|×)?\s*(\d+)", s)
    if m:
        return int(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*reps", s)
    if m:
        return None, float(m.group(1))
    if "amrap" in s or "max rep" in s or "to failure" in s:
        return None, 18.0
    return None, None


def _parse_rest_s(text: str) -> int | None:
    """Parse rest seconds from '60s', '2min', '90s', '3-5 min', '2m'."""
    s = (text or "").lower()
    rng = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*m", s)
    if rng:
        return int(rng.group(1)) * 60
    m = re.search(r"(\d+(?:\.\d+)?)\s*min", s)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.search(r"(\d+)\s*s", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*m\b", s)
    if m:
        return int(m.group(1)) * 60
    return None


def _classify(reps, rest_s, is_duration, name, patterns, section) -> str:
    n = (name or "").lower()
    pats = [p.lower() for p in (patterns or [])]

    if section == "cooldown":
        return "mobility"
    if any(h in n for h in _MOBILITY_HINTS) or any(
        ("mobility" in p or "stretch" in p) for p in pats
    ):
        return "mobility"
    if is_duration or any(any(c in p for c in _CONDITIONING_PATTERNS) for p in pats):
        return "power" if any(h in n for h in _POWER_HINTS) else "conditioning"
    if any(h in n for h in _POWER_HINTS):
        return "power"
    if reps is None:
        return "hypertrophy"  # unknown rep scheme → assume moderate
    if reps <= 5:
        # Low rep = strength, but very short rest reads as density/power
        return "max_strength"
    if reps <= 12:
        return "hypertrophy"
    if reps <= 20:
        return "strength_endurance"
    return "conditioning"


def analyze_canvas(items: list[dict]) -> dict:
    """
    Analyze a list of canvas items and return the actual training profile.

    items: [{exercise_id, name, section, sets_reps, rest, intensity}]
    """
    from app.data.loader import load_exercises

    catalog = {e.id: e for e in load_exercises()}

    scores = {a: 0.0 for a in ADAPTATIONS}
    rep_hist = {"1-5": 0, "6-12": 0, "13-20": 0, "20+": 0, "time": 0}
    per_section = {"warmup": 0, "main": 0, "cooldown": 0}
    total_sets = 0
    n_items = 0

    for it in items:
        ex = catalog.get(it.get("exercise_id"))
        name = (ex.name if ex else it.get("name")) or ""
        patterns = ex.movement_patterns if ex else []
        is_duration = bool(ex.is_duration) if ex else False
        section = it.get("section") or "main"
        per_section[section] = per_section.get(section, 0) + 1
        n_items += 1

        sets, reps = _parse_sets_reps(it.get("sets_reps", ""))
        rest_s = _parse_rest_s(it.get("rest", ""))

        # A time-based scheme ("2 x 30s", "45 sec") is a hold/duration, not reps.
        if re.search(r"\d+\s*(?:s|sec|secs|min)\b", (it.get("sets_reps", "") or "").lower()):
            is_duration = True
            reps = None

        weight = float(sets or 3)
        total_sets += int(weight)

        adapt = _classify(reps, rest_s, is_duration, name, patterns, section)
        scores[adapt] += weight

        # rep histogram (working-set ranges)
        if is_duration or reps is None:
            rep_hist["time" if is_duration else "6-12"] += 1
        elif reps <= 5:
            rep_hist["1-5"] += 1
        elif reps <= 12:
            rep_hist["6-12"] += 1
        elif reps <= 20:
            rep_hist["13-20"] += 1
        else:
            rep_hist["20+"] += 1

    total_weight = sum(scores.values()) or 1.0

    # Adaptation scores as 0-100 proportions of total weighted work.
    adaptation_scores = {
        a: round(100 * scores[a] / total_weight) for a in ADAPTATIONS
    }

    # Primary adaptation = top NON-mobility bucket (the session's training goal),
    # unless the whole thing is mobility/recovery.
    non_mobility = {a: scores[a] for a in ADAPTATIONS if a != "mobility"}
    if sum(non_mobility.values()) == 0:
        primary = "mobility"
    else:
        primary = max(non_mobility, key=non_mobility.get)

    # Independent 0-100 stimulus gauges (reuse the generator's gauge UI).
    gauges = {"strength": 0.0, "conditioning": 0.0, "mobility": 0.0}
    for a in ADAPTATIONS:
        ws, wc, wm = _STIMULUS_WEIGHTS[a]
        frac = scores[a] / total_weight
        gauges["strength"] += ws * frac
        gauges["conditioning"] += wc * frac
        gauges["mobility"] += wm * frac
    stimulus_distribution = {k: round(100 * v) for k, v in gauges.items()}

    verdict, tip = _VERDICT[primary]

    return {
        "total_exercises": n_items,
        "total_sets": total_sets,
        "per_section": per_section,
        "rep_histogram": rep_hist,
        "adaptation_scores": adaptation_scores,
        "primary_adaptation": primary,
        "primary_label": ADAPTATION_LABEL[primary],
        "stimulus_distribution": stimulus_distribution,
        "verdict": verdict,
        "tip": tip,
    }
