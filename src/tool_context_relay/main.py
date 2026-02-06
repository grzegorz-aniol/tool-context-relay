from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI

from tool_context_relay.agent.handler import RunHookHandler
from tool_context_relay.boxing import BoxingMode
from tool_context_relay.openai_env import (
    ProfileConfig,
    apply_profile,
    load_profile,
)

from tool_context_relay.agent.agent import build_agent
from tool_context_relay.agent.context import RelayContext


def run_once(
    *,
    prompt: str,
    model: str,
    initial_kv: dict[str, str],
    profile: str = "openai",
    profile_config: ProfileConfig | None = None,
    print_tools: bool = False,
    fewshots: bool = True,
    temperature: float | None = None,
    boxing_mode: BoxingMode = "opaque",
    hooks: object | None = None,
) -> tuple[str, RelayContext]:
    from agents import OpenAIChatCompletionsModel, Runner, set_tracing_disabled

    load_dotenv(verbose=True)
    profile_config = profile_config or load_profile(profile)
    apply_profile(profile_config)
    resolved_provider = profile_config.provider
    if resolved_provider == "openai-compat":
        # OpenAI-compatible servers typically do not support the OpenAI tracing backend.
        # Disabling tracing avoids confusing non-fatal 401s when OPENAI_API_KEY isn't set.
        set_tracing_disabled(True)

    if profile_config.api_key is None:
        raise RuntimeError(f"profile '{profile_config.name}' does not specify an API key")
    base_url = profile_config.endpoint
    client = (
        AsyncOpenAI(base_url=base_url, api_key=profile_config.api_key)
        if base_url is not None
        else AsyncOpenAI(api_key=profile_config.api_key)
    )
    model_obj = OpenAIChatCompletionsModel(model=model, openai_client=client)

    context = RelayContext(kv=dict(initial_kv), boxing_mode=boxing_mode)
    agent = build_agent(
        model=model_obj,
        fewshots=fewshots,
        temperature=temperature,
        boxing_mode=boxing_mode,
    )
    if print_tools:
        from tool_context_relay.agent.tool_definitions import print_tool_definitions

        print_tool_definitions(agent.tools, stream=sys.stderr)
    if hooks is None:
        hooks = RunHookHandler()
    result = Runner.run_sync(agent, prompt, hooks=hooks, context=context)
    return result.final_output, context
