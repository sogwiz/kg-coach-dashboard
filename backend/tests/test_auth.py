"""
Tests for the mock coach auth endpoints — Phase 8.

Covers:
  - POST /api/auth/login — success path, missing fields, empty credentials
  - GET  /api/auth/me   — valid token, missing header, bad token
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


def test_login_returns_token_and_profile() -> None:
    """Any non-empty email + password combination produces a token."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "coach@example.com", "password": "secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert len(body["token"]) > 0
    coach = body["coach"]
    assert coach["role"] == "coach"
    assert "name" in coach
    assert "email" in coach
    assert "coach_id" in coach


def test_login_empty_email_rejected() -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "", "password": "secret"},
    )
    assert resp.status_code == 400


def test_login_empty_password_rejected() -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "coach@example.com", "password": ""},
    )
    assert resp.status_code == 400


def test_login_produces_unique_tokens() -> None:
    """Each login call should return a different token."""
    r1 = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw"})
    r2 = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw"})
    assert r1.json()["token"] != r2.json()["token"]


# ---------------------------------------------------------------------------
# /me tests
# ---------------------------------------------------------------------------


def test_me_returns_profile_for_valid_token() -> None:
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "coach@example.com", "password": "pw"},
    )
    token = login_resp.json()["token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert profile["role"] == "coach"
    assert "name" in profile


def test_me_rejects_unknown_token() -> None:
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer totally-fake-token-xyz"},
    )
    assert resp.status_code == 401


def test_me_rejects_malformed_header() -> None:
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": "notbearer abc"},
    )
    assert resp.status_code == 401


def test_me_requires_authorization_header() -> None:
    resp = client.get("/api/auth/me")
    # FastAPI returns 422 when a required Header param is missing
    assert resp.status_code == 422
