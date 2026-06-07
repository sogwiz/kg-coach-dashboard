"""
Observability — LangSmith tracing helpers (Phase 7).

Two public symbols:

  langsmith_enabled() -> bool
      Returns True when LANGCHAIN_TRACING_V2=true AND LANGCHAIN_API_KEY is set.
      Never raises; safe to call at any time.

  tracing_config(run_name, **metadata) -> RunnableConfig
      Returns a RunnableConfig that enables LangSmith tracing when the
      env vars are present, or a minimal no-op config when they are not.
      Never raises; degrades gracefully when tracing is unavailable.

Usage (generator):
    from app.observability.tracing import tracing_config
    plan = structured_llm.invoke(messages, config=tracing_config(
        "structure_plan",
        member_id=member_id,
        variant_id=variant_id,
        prompt=prompt,
    ))

Usage (copilot agent):
    result = agent.invoke(
        {"messages": [...]},
        config=tracing_config("copilot_chat", member_id=member_id),
    )
"""

from __future__ import annotations

import os

from langchain_core.runnables import RunnableConfig


def langsmith_enabled() -> bool:
    """
    Return True when LangSmith tracing is configured.

    Requires both:
      - LANGCHAIN_TRACING_V2=true  (case-insensitive)
      - LANGCHAIN_API_KEY set to a non-empty value

    Returns False in all other cases — never raises.
    """
    tracing = os.environ.get("LANGCHAIN_TRACING_V2", "").strip().lower()
    api_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    return tracing == "true" and bool(api_key)


def tracing_config(run_name: str, **metadata: object) -> RunnableConfig:
    """
    Build a RunnableConfig for LangChain/LangGraph invocations.

    When LangSmith is enabled (LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY),
    the returned config tags the run with ``run_name`` and the supplied
    metadata key/value pairs so the trace appears in the LangSmith dashboard
    with useful labels (member_id, variant_id, prompt, etc.).

    When LangSmith is disabled, returns a minimal config with just run_name
    for in-process tracing context.  Never crashes — tracing failure must
    NEVER break the application.

    Parameters
    ----------
    run_name:
        The name shown for this run in LangSmith, e.g. "structure_plan" or
        "copilot_chat".
    **metadata:
        Arbitrary key/value pairs attached as LangSmith metadata.  Common
        keys: member_id, variant_id, prompt.

    Returns
    -------
    RunnableConfig
        A dict-like config suitable for passing to .invoke() / .ainvoke().
    """
    try:
        config: RunnableConfig = {"run_name": run_name}
        if langsmith_enabled():
            config["metadata"] = {str(k): str(v) for k, v in metadata.items()}
            project = os.environ.get("LANGCHAIN_PROJECT", "").strip()
            if project:
                config["tags"] = [project]
        return config
    except Exception:
        # Absolute last-resort: return empty config to avoid crashing the app
        return {}
