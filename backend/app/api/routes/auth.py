"""
Mock coach authentication routes — Phase 8.

Endpoints:
  POST /api/auth/login  — accepts any coach credentials, returns a stub token + coach profile
  GET  /api/auth/me     — returns the coach profile for a valid stub token

This is an intentionally simple in-memory mock.  No real identity provider,
no hashing, no JWT signature verification.  The token is just a UUID stored
in a module-level dict for the lifetime of the process.

Design note: "mock auth is fine" per the Phase 8 scope.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Hardcoded coach profile
# ---------------------------------------------------------------------------

_COACH_PROFILE = {
    "coach_id": "coach_001",
    "name": "Alex Coach",
    "email": "alex@coachplatform.com",
    "role": "coach",
    "avatar_initials": "AC",
}

# In-memory token store:  token -> coach_profile dict
_token_store: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class CoachProfile(BaseModel):
    coach_id: str
    name: str
    email: str
    role: str
    avatar_initials: str


class LoginResponse(BaseModel):
    token: str
    coach: CoachProfile


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """
    Mock login endpoint.

    Accepts any non-empty email + password combination and returns a stub
    bearer token paired with the hardcoded coach profile.  In a real system
    this would validate credentials against a user store.
    """
    if not body.email.strip() or not body.password.strip():
        raise HTTPException(status_code=400, detail="email and password are required")

    token = str(uuid.uuid4())
    _token_store[token] = _COACH_PROFILE.copy()

    return LoginResponse(
        token=token,
        coach=CoachProfile(**_COACH_PROFILE),
    )


@router.get("/me", response_model=CoachProfile)
async def me(authorization: str = Header(...)) -> CoachProfile:
    """
    Return the coach profile for a valid stub token.

    Expects an Authorization header of the form ``Bearer <token>``.
    Returns 401 if the header is missing, malformed, or the token is unknown.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.removeprefix("Bearer ").strip()

    profile = _token_store.get(token)
    if profile is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return CoachProfile(**profile)
