"""
FastAPI application entry point.

Phase 1: minimal shell with CORS + health check.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, copilot, generator, graph, injury, members

app = FastAPI(
    title="KG Coach Dashboard API",
    version="0.1.0",
    description="Knowledge-Graph-Backed Coach Dashboard — Backend API",
)

# Allow the Vite dev server (port 5173) and any local origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns {"status": "ok"}."""
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(injury.router, prefix="/api")
app.include_router(generator.router, prefix="/api")
app.include_router(copilot.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
