from pydantic import BaseModel, Field


class Exercise(BaseModel):
    """
    Pydantic model for a single exercise from the catalog.

    The 14 fields come directly from data/exercises.json.
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
