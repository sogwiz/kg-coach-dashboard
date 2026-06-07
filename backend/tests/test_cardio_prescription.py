"""
Cardio machines must be prescribed by calories / distance / time + intensity —
never by reps. "16 reps on a SkiErg" is a domain error.

These are deterministic assembler unit tests (no LLM, no API key needed).
"""

from __future__ import annotations

from app.models.exercise import Exercise
from app.generator.assembler import _scheme, _is_cardio_machine


def _ex(name: str, patterns: list[str]) -> Exercise:
    return Exercise(id=name.lower().replace(" ", "_"), name=name, movement_patterns=patterns)


SKIERG = _ex("SkiErg", ["cardio - locomotion", "cardio", "total body"])
ROWER = _ex("Rowing Ergometer (Concept2)", ["upper pull - horizontal", "cardio"])
ASSAULT = _ex("Assault Bike (Max Effort)", ["cardio", "total body"])
RUN = _ex("Run (Outdoor / Treadmill)", ["cardio - locomotion", "cardio"])
ZONE2 = _ex("Zone-2 Steady State Bike", ["cardio", "cardio - locomotion"])
SQUAT = _ex("Back Squat", ["lower push - squat"])
PLANK = _ex("Forearm Plank", ["core - anti-extension"])


class TestCardioDetection:
    def test_ergs_and_locomotion_are_cardio(self):
        for ex in (SKIERG, ROWER, ASSAULT, RUN, ZONE2):
            assert _is_cardio_machine(ex), f"{ex.name} should be detected as cardio"

    def test_resistance_is_not_cardio(self):
        assert not _is_cardio_machine(SQUAT)
        assert not _is_cardio_machine(PLANK)


class TestCardioPrescription:
    def test_skierg_is_not_rep_based(self):
        s = _scheme("conditioning", "conditioning", SKIERG, 1.0)
        assert s["reps"] is None, "SkiErg must never be prescribed in reps"
        assert s["calories"] is not None, "ergs are prescribed in calories"
        assert s["intensity_pct"] is not None, "cardio must carry an intensity %"

    def test_rower_uses_calories(self):
        s = _scheme("conditioning", "conditioning", ROWER, 1.0)
        assert s["reps"] is None
        assert s["calories"] and s["distance_meters"] is None

    def test_run_uses_distance(self):
        s = _scheme("conditioning", "conditioning", RUN, 1.0)
        assert s["reps"] is None
        assert s["distance_meters"] and s["calories"] is None

    def test_zone2_is_steady_state_block(self):
        s = _scheme("conditioning", "conditioning", ZONE2, 1.0)
        assert s["reps"] is None
        assert s["sets"] == 1 and s["duration_seconds"] and s["intensity_pct"] == 65

    def test_endurance_mode_collapses_to_steady_block(self):
        s = _scheme("endurance", "conditioning", SKIERG, 1.0)
        assert s["sets"] == 1 and s["duration_seconds"] and s["reps"] is None

    def test_resistance_still_uses_reps_without_intensity(self):
        s = _scheme("strength", "compound", SQUAT, 1.0)
        assert s["reps"] == 5 and s["calories"] is None and s["distance_meters"] is None

    def test_exactly_one_work_metric_for_cardio(self):
        for ex in (SKIERG, ROWER, ASSAULT, RUN):
            s = _scheme("conditioning", "conditioning", ex, 1.0)
            metrics = [s["reps"], s["duration_seconds"], s["distance_meters"], s["calories"]]
            assert sum(m is not None for m in metrics) == 1, f"{ex.name}: exactly one work metric"
