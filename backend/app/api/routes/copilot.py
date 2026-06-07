"""
Copilot API route — Phase 7.

POST /api/copilot/chat
    Multi-member-aware chat endpoint.  Accepts a coach message + member_id,
    invokes the LangGraph tool-calling agent, and streams the response.

    When ANTHROPIC_API_KEY is not set, returns HTTP 503 with a clear message.
    When the agent is unavailable for any other reason, returns HTTP 500.

Streaming
---------
The response is a StreamingResponse with content-type text/plain.
Each streamed chunk is a partial response string.  The frontend (Phase 10)
reads the stream as Server-Sent Events or raw text.

LangSmith tracing
-----------------
Each invocation passes a RunnableConfig from tracing_config() so Copilot
runs appear as named, member-tagged traces in the LangSmith dashboard.
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/copilot", tags=["copilot"])


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class CopilotRequest(BaseModel):
    """
    POST /api/copilot/chat request body.

    Attributes
    ----------
    message:
        The coach's question or command.
    member_id:
        The member the coach is asking about.
    """

    message: str = Field(min_length=1, max_length=2000)
    member_id: str = Field(default="mbr_01HX9JORDAN")


# ---------------------------------------------------------------------------
# Shared singletons
# ---------------------------------------------------------------------------


def _build_agent(member_id: str):
    """
    Build the copilot agent for the given member.

    Returns the compiled LangGraph agent, or None if the LLM is unavailable.
    """
    from app.copilot.agent import create_copilot_agent, get_copilot_llm
    from app.data.loader import load_member_context
    from app.graph.member_kg import MemberKG
    from app.ontology.catalog import build_concept_catalog

    llm = get_copilot_llm()
    if llm is None:
        return None

    try:
        member = load_member_context(member_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{member_id}' not found.",
        )

    concepts = build_concept_catalog()
    member_kg = MemberKG(member, concepts)
    return create_copilot_agent(member_kg, llm)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat")
async def chat(request: CopilotRequest) -> StreamingResponse:
    """
    Run the Copilot agent and stream the response.

    The agent may call one or more tools (adherence_trend, morning_brief,
    injury_status, sleep_summary, current_workout_plan) before generating
    a final response.

    Streams text/plain — each chunk is a partial response string.
    """
    # Check LLM availability
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Set the environment variable and restart the server."
            ),
        )

    agent = _build_agent(request.member_id)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Copilot agent could not be initialised. Check ANTHROPIC_API_KEY.",
        )

    from app.observability.tracing import tracing_config

    run_cfg = tracing_config(
        "copilot_chat",
        member_id=request.member_id,
        message_preview=request.message[:80],
    )

    async def _stream() -> AsyncIterator[str]:
        """Stream the agent's final response text, chunk by chunk."""
        try:
            # Use astream_events for streaming the final response
            final_text = ""
            async for event in agent.astream_events(
                {"messages": [("human", request.message)]},
                config=run_cfg,
                version="v2",
            ):
                # We only stream the final AI message content
                if (
                    event["event"] == "on_chat_model_stream"
                    and event.get("metadata", {}).get("langgraph_node") == "agent"
                ):
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        if isinstance(content, str):
                            yield content
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    yield block.get("text", "")
                                elif isinstance(block, str):
                                    yield block
        except Exception as exc:
            yield f"\n[Error: {exc}]"

    return StreamingResponse(
        _stream(),
        media_type="text/plain",
        headers={"X-Member-Id": request.member_id},
    )


@router.post("/chat/sync", response_model=None)
async def chat_sync(request: CopilotRequest) -> dict:
    """
    Non-streaming variant of /chat — returns the full response as JSON.

    Useful for testing and for frontends that don't support streaming.
    Returns HTTP 503 if ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Set the environment variable and restart the server."
            ),
        )

    agent = _build_agent(request.member_id)
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Copilot agent could not be initialised.",
        )

    from app.observability.tracing import tracing_config

    run_cfg = tracing_config(
        "copilot_chat_sync",
        member_id=request.member_id,
        message_preview=request.message[:80],
    )

    try:
        result = await agent.ainvoke(
            {"messages": [("human", request.message)]},
            config=run_cfg,
        )
        # Extract the final AI message text
        messages = result.get("messages", [])
        final_message = messages[-1] if messages else None
        response_text = ""
        if final_message:
            if hasattr(final_message, "content"):
                content = final_message.content
                if isinstance(content, str):
                    response_text = content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            response_text += block.get("text", "")
                        elif isinstance(block, str):
                            response_text += block

        return {
            "member_id": request.member_id,
            "message": request.message,
            "response": response_text,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {exc}",
        )
