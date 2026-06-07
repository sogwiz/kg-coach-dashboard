"""
Copilot API route — Phase 7 + 7.1 (R2/R3 gap-closing).

POST /api/copilot/chat
    Multi-member-aware chat endpoint.  Accepts a coach message + member_id +
    optional image attachments, invokes the LangGraph tool-calling agent, and
    streams the response.

    Phase 7.1 additions:
      - CopilotRequest accepts attachments: list[ChatAttachment] for multimodal.
      - The agent is compiled with a MemorySaver checkpointer.  The thread_id
        defaults to member_id so multi-turn context persists per member.
      - On the first turn, seed/replay the member's stored chat_history into
        the conversation so prior messages are part of the thread context.
      - Image attachments are passed to the model as Anthropic vision content
        blocks.  Degrades gracefully when no attachments are provided.

    When ANTHROPIC_API_KEY is not set, returns HTTP 503 with a clear message.

GET /api/copilot/members/{member_id}/chat-history
    Returns the member's stored chat transcript (from seed data) as a list of
    ChatMessage objects, including any inline images/attachments for the UI.

Streaming
---------
The /chat response is a StreamingResponse with content-type text/plain.
Each streamed chunk is a partial response string.

LangSmith tracing
-----------------
Each invocation passes a RunnableConfig from tracing_config() so Copilot
runs appear as named, member-tagged traces in the LangSmith dashboard.
"""

from __future__ import annotations

import os
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/copilot", tags=["copilot"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatAttachment(BaseModel):
    """
    An image or file attachment on a chat message.

    Attributes
    ----------
    type:
        MIME-like type string, e.g. "image/png", "image/jpeg".
        Used to build Anthropic vision content blocks.
    url:
        Optional URL or base64 data-URI for the image content.
        When provided, the image is passed to the vision model.
    caption:
        Optional human-readable caption for the attachment.
    """

    type: str = Field(default="image")
    url: str | None = None
    caption: str | None = None


class CopilotRequest(BaseModel):
    """
    POST /api/copilot/chat request body.

    Attributes
    ----------
    message:
        The coach's question or command.
    member_id:
        The member the coach is asking about.
    attachments:
        Optional list of image attachments (multimodal — R2).
        Each attachment may carry a URL/base64 and a caption.
        Passed as Anthropic vision content blocks when present.
    """

    message: str = Field(min_length=1, max_length=2000)
    member_id: str = Field(default="mbr_01HX9JORDAN")
    attachments: list[ChatAttachment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# In-memory seed-tracking (first-turn history seeding per thread)
# ---------------------------------------------------------------------------

# Tracks which member threads have already been seeded with chat history.
# Key: thread_id (= member_id).  Value: True once seeded.
_seeded_threads: set[str] = set()

# Agent singletons — one compiled agent per member (reused across turns).
# The MemorySaver checkpointer is embedded in the agent; we keep a reference
# here so the same checkpointer instance is used across requests.
_agent_cache: dict[str, "Any"] = {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_agent(member_id: str):
    """
    Build (or retrieve cached) the copilot agent for the given member.

    The agent is cached so the MemorySaver checkpointer persists between
    HTTP requests for the same member (enabling multi-turn memory).

    Returns the compiled LangGraph agent, or None if the LLM is unavailable.
    """
    if member_id in _agent_cache:
        return _agent_cache[member_id]

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
    agent = create_copilot_agent(member_kg, llm)

    if agent is not None:
        _agent_cache[member_id] = agent

    return agent


def _build_human_content(message: str, attachments: list[ChatAttachment]) -> list | str:
    """
    Build the HumanMessage content for the agent.

    If there are image attachments with URLs, builds an Anthropic-compatible
    multimodal content list (text block + image blocks).  Otherwise returns
    the plain text string (no overhead).

    Parameters
    ----------
    message:
        The plain-text question from the coach.
    attachments:
        List of ChatAttachment objects from the request.

    Returns
    -------
    str or list
        Plain string when no images; list of content blocks when images present.
    """
    image_attachments = [a for a in attachments if a.url and a.type.startswith("image")]
    if not image_attachments:
        return message

    content: list = [{"type": "text", "text": message}]
    for att in image_attachments:
        url = att.url
        if url.startswith("data:"):
            # base64 data URI: data:image/jpeg;base64,<data>
            try:
                header, data = url.split(",", 1)
                media_type = header.split(";")[0].split(":")[1]
            except Exception:
                media_type = att.type
                data = url
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })
        else:
            # Public URL
            content.append({
                "type": "image",
                "source": {
                    "type": "url",
                    "url": url,
                },
            })

    return content


async def _seed_thread_if_needed(
    agent,
    member_id: str,
    thread_id: str,
    run_cfg: dict,
) -> None:
    """
    Seed the conversation thread with the member's stored chat history on
    the first turn (R2 — seed past history).

    Uses the agent's update_state method to inject historical messages into
    the MemorySaver checkpointer so they become part of the thread context
    before the first user message is processed.

    This is a no-op after the first call for a given thread_id.
    """
    if thread_id in _seeded_threads:
        return

    _seeded_threads.add(thread_id)

    from app.copilot.agent import _seed_messages_for_member

    seed_msgs = _seed_messages_for_member(member_id)
    if not seed_msgs:
        return

    # Inject seed messages as the initial thread state
    try:
        agent.update_state(
            config={"configurable": {"thread_id": thread_id}},
            values={"messages": seed_msgs},
        )
    except Exception:
        # If update_state fails (e.g. different LangGraph version), continue
        # without seeding — the agent will still work for the current turn.
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def chat(request: CopilotRequest) -> StreamingResponse:
    """
    Run the Copilot agent and stream the response.

    Phase 7.1:
      - Thread-keyed by member_id for conversation memory (MemorySaver).
      - Seeds prior chat_history on the first turn for each member thread.
      - Passes image attachments as Anthropic vision content blocks.

    Streams text/plain — each chunk is a partial response string.
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
            detail="Copilot agent could not be initialised. Check ANTHROPIC_API_KEY.",
        )

    from app.observability.tracing import tracing_config

    thread_id = request.member_id  # per-member thread
    run_cfg = tracing_config(
        "copilot_chat",
        member_id=request.member_id,
        message_preview=request.message[:80],
    )
    # Merge thread_id into configurable for MemorySaver
    run_cfg = dict(run_cfg)
    run_cfg.setdefault("configurable", {})["thread_id"] = thread_id

    # Seed history on first turn (R2 — seed past history)
    await _seed_thread_if_needed(agent, request.member_id, thread_id, run_cfg)

    # Build human content (text + optional image blocks)
    human_content = _build_human_content(request.message, request.attachments)

    async def _stream() -> AsyncIterator[str]:
        """Stream the agent's final response text, chunk by chunk."""
        try:
            async for event in agent.astream_events(
                {"messages": [("human", human_content)]},
                config=run_cfg,
                version="v2",
            ):
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

    Phase 7.1: thread-keyed by member_id (conversation memory); seeds
    chat_history on first turn; supports image attachments.

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

    thread_id = request.member_id
    run_cfg = tracing_config(
        "copilot_chat_sync",
        member_id=request.member_id,
        message_preview=request.message[:80],
    )
    run_cfg = dict(run_cfg)
    run_cfg.setdefault("configurable", {})["thread_id"] = thread_id

    # Seed history on first turn
    await _seed_thread_if_needed(agent, request.member_id, thread_id, run_cfg)

    human_content = _build_human_content(request.message, request.attachments)

    try:
        result = await agent.ainvoke(
            {"messages": [("human", human_content)]},
            config=run_cfg,
        )
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


@router.get("/members/{member_id}/chat-history")
async def get_chat_history(member_id: str) -> list[dict]:
    """
    GET /api/copilot/members/{member_id}/chat-history

    Return the member's stored chat history transcript (from seed data) as an
    ordered list of chat messages — newest last.  The UI uses this to render
    the historical transcript panel (including inline images) before the first
    new turn.

    Each message contains:
      - ts:          ISO timestamp string
      - from:        "member" or "coach"
      - text:        message text
      - attachments: list of {type, caption} dicts (images for multimodal)

    Returns HTTP 404 if the member_id is not found.
    Returns an empty list [] if the member has no chat history.
    """
    from app.data.loader import load_member_context
    from app.graph.member_kg import MemberKG
    from app.ontology.catalog import build_concept_catalog

    try:
        member = load_member_context(member_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{member_id}' not found.",
        )

    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)
    messages = mkg.get_chat_history()

    # Sort oldest → newest for the UI transcript view
    messages_sorted = sorted(messages, key=lambda m: m.ts)

    return [
        {
            "ts": m.ts,
            "from": m.from_,
            "text": m.text,
            "attachments": [
                {"type": a.type, "caption": a.caption}
                for a in m.attachments
            ],
        }
        for m in messages_sorted
    ]
