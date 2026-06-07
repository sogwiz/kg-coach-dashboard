"""
Canvas API — analyze a coach-built Creative Canvas.

POST /api/canvas/analyze
    Given the exercises + sets/reps/rest schemes the coach composed, return the
    ACTUAL training adaptations + stimulus (deterministic; no LLM). Lets the
    coach compare intended vs actual.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/canvas", tags=["canvas"])


class CanvasItem(BaseModel):
    exercise_id: str = ""
    name: str = ""
    section: str = "main"  # warmup | main | cooldown
    sets_reps: str = ""
    rest: str = ""
    intensity: str = ""


class CanvasAnalyzeRequest(BaseModel):
    items: list[CanvasItem] = Field(default_factory=list)


@router.post("/analyze", response_model=None)
async def analyze(request: CanvasAnalyzeRequest) -> dict:
    """Return the workout's actual adaptation/stimulus profile."""
    from app.generator.synthesize import analyze_canvas

    return analyze_canvas([i.model_dump() for i in request.items])
