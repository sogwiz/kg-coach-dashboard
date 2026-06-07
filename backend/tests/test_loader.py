"""
Phase 1 validation: exercises load as 50 records, member loads with all 11 sections.
"""

from app.data.loader import load_exercises, load_member_context


def test_exercises_load_50_records():
    exercises = load_exercises()
    assert len(exercises) == 50, f"Expected 50 exercises, got {len(exercises)}"


def test_exercises_have_required_fields():
    exercises = load_exercises()
    for ex in exercises:
        assert ex.id, f"Exercise missing id: {ex}"
        assert ex.name, f"Exercise missing name: {ex}"
        # All 14 fields should be present (even if empty lists / None)
        assert hasattr(ex, "muscle_groups")
        assert hasattr(ex, "joints_loaded")
        assert hasattr(ex, "movement_patterns")
        assert hasattr(ex, "equipment_required")
        assert hasattr(ex, "is_bilateral")
        assert hasattr(ex, "side")
        assert hasattr(ex, "priority_tier")
        assert hasattr(ex, "is_reps")
        assert hasattr(ex, "is_duration")
        assert hasattr(ex, "supports_weight")
        assert hasattr(ex, "estimated_rep_duration")
        assert hasattr(ex, "bilateral_pair_id")


def test_member_loads_with_all_sections():
    """
    The member-context.json has 11 meaningful sections (excluding _note):
      profile, goals, preferences, equipment_available, injuries,
      workout_history, adherence, biomarkers, labs, chat_history, coach_brief
    """
    member = load_member_context()

    # Profile
    assert member.profile is not None
    assert member.profile.id == "mbr_01HX9JORDAN"
    assert member.profile.name == "Jordan Rivera"

    # Goals — at least 1
    assert len(member.goals) >= 1

    # Preferences
    assert member.preferences is not None
    assert member.preferences.preferred_session_minutes > 0

    # Equipment available
    assert len(member.equipment_available) >= 1

    # Injuries
    assert len(member.injuries) >= 1
    assert member.injuries[0].joint == "knee"

    # Workout history
    assert len(member.workout_history) >= 1

    # Adherence
    assert member.adherence is not None
    assert len(member.adherence.weekly_completion_pct) >= 1

    # Biomarkers
    assert member.biomarkers is not None
    assert member.biomarkers.resting_hr_bpm > 0

    # Labs
    assert member.labs is not None

    # Chat history
    assert len(member.chat_history) >= 1

    # Coach brief
    assert member.coach_brief is not None
    assert len(member.coach_brief.morning_tasks) >= 1


def test_member_has_exactly_11_sections():
    """
    Explicit check that all 11 expected sections are non-None / non-empty.
    """
    member = load_member_context()
    sections = {
        "profile": member.profile,
        "goals": member.goals,
        "preferences": member.preferences,
        "equipment_available": member.equipment_available,
        "injuries": member.injuries,
        "workout_history": member.workout_history,
        "adherence": member.adherence,
        "biomarkers": member.biomarkers,
        "labs": member.labs,
        "chat_history": member.chat_history,
        "coach_brief": member.coach_brief,
    }
    assert len(sections) == 11
    for name, val in sections.items():
        assert val is not None, f"Section '{name}' is None"
