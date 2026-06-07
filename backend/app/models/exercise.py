from typing import Literal

from pydantic import BaseModel, Field

MovementType = Literal["flexion", "extension", "rotation", "load", "impact"]


class Exercise(BaseModel):
    """
    Pydantic model for a single exercise from the catalog.

    The 14 fields come directly from data/exercises.json.
    joint_movements is loaded separately from data/exercise_movements.json
    and merged in at load time.
    """

    id: str
    name: str
    muscle_groups: list[str] = Field(default_factory=list)
    joints_loaded: list[str] = Field(default_factory=list)
    movement_patterns: list[str] = Field(default_factory=list)
    equipment_required: list[str] = Field(default_factory=list)
    is_bilateral: bool = False
    side: str | None = None
    priority_tier: int = 2
    is_reps: bool = True
    is_duration: bool = False
    supports_weight: bool = False
    estimated_rep_duration: float = 0.0
    bilateral_pair_id: str | None = None
    # Movement-type annotations: joint -> list of movement types this exercise
    # demands at that joint.  Populated from data/exercise_movements.json.
    # Example: {"knee": ["flexion", "load"], "hip": ["flexion", "load"]}
    joint_movements: dict[str, list[MovementType]] = Field(default_factory=dict)
