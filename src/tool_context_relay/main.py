from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI

from tool_context_relay.agent.handler import RunHookHandler
from tool_context_relay.openai_env import (
    Provider,
    apply_api_key_override,
    resolve_provider,
)

from tool_context_relay.agent.agent import build_agent
from tool_context_relay.agent.context import RelayContext


def run_once(
    *,
    prompt: str,
    model: str,
    initial_kv: dict[str, str],
    provider: Provider = "auto",
    print_tools: bool = False,
    fewshots: bool = True,
    hooks: object | None = None,
) -> tuple[str, RelayContext]:
    from agents import OpenAIChatCompletionsModel, Runner, set_tracing_disabled

    load_dotenv(verbose=True)
    apply_api_key_override(provider=provider)

    resolved_provider = resolve_provider(provider)
    if resolved_provider == "openai-compat":
        # OpenAI-compatible servers typically do not support the OpenAI tracing backend.
        # Disabling tracing avoids confusing non-fatal 401s when OPENAI_API_KEY isn't set.
        set_tracing_disabled(True)

    base_url = (
        (os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or "").strip()
        or None
    )
    if resolved_provider == "openai-compat" and base_url is None:
        raise RuntimeError(
            "Provider 'openai-compat' requires OPENAI_BASE_URL/OPENAI_API_BASE to be set."
        )

    client = (
        AsyncOpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY") or "EMPTY")
        if base_url is not None
        else AsyncOpenAI()
    )
    model_obj = OpenAIChatCompletionsModel(model=model, openai_client=client)

    context = RelayContext(kv=dict(initial_kv))
    agent = build_agent(model=model_obj, fewshots=fewshots)
    if print_tools:
        from tool_context_relay.agent.tool_definitions import print_tool_definitions

        print_tool_definitions(agent.tools, stream=sys.stderr)
    if hooks is None:
        hooks = RunHookHandler()
    result = Runner.run_sync(agent, prompt, hooks=hooks, context=context)
    return result.final_output, context
