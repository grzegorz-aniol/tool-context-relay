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


def _build_model_settings(
    *,
    temperature: float | None,
    provider: str,
    backend_provider: str | None,
) -> object | None:
    from agents import ModelSettings

    model_settings: ModelSettings | None = None
    if temperature is not None:
        model_settings = ModelSettings(temperature=temperature)

    metadata: dict[str, object] | None = None
    if provider == "openrouter":
        metadata = {
            "allow_fallbacks": False,
            "data_collection": "deny",
        }

    if metadata is not None:
        payload = dict(metadata)
        if backend_provider:
            payload["order"] = [backend_provider]
        provider_settings = ModelSettings(extra_body={"provider": payload})
        model_settings = (
            provider_settings
            if model_settings is None
            else model_settings.resolve(provider_settings)
        )

    return model_settings


def run_once(
    *,
    prompt: str,
    model: str,
    profile: str = "openai",
    profile_config: ProfileConfig | None = None,
    print_tools: bool = False,
    fewshots: bool = True,
    temperature: float | None = None,
    boxing_mode: BoxingMode = "opaque",
    hooks: object | None = None,
    max_retries: int | None = None,
) -> tuple[str, RelayContext]:
    from agents import OpenAIChatCompletionsModel, Runner, set_tracing_disabled

    load_dotenv(verbose=True)
    profile_config = profile_config or load_profile(profile)
    apply_profile(profile_config)
    resolved_provider = profile_config.provider
    if resolved_provider != "openai":
        # OpenAI-compatible servers typically do not support the OpenAI tracing backend.
        # Disabling tracing avoids confusing non-fatal 401s when OPENAI_API_KEY isn't set.
        set_tracing_disabled(True)

    model_settings = _build_model_settings(
        temperature=temperature,
        provider=resolved_provider,
        backend_provider=profile_config.backend_provider,
    )

    if profile_config.api_key is None:
        raise RuntimeError(f"profile '{profile_config.name}' does not specify an API key")
    base_url = profile_config.endpoint
    client_kwargs: dict[str, object] = {"api_key": profile_config.api_key}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    if max_retries is not None:
        client_kwargs["max_retries"] = max_retries
    client = AsyncOpenAI(**client_kwargs)
    model_obj = OpenAIChatCompletionsModel(model=model, openai_client=client)

    context = RelayContext(boxing_mode=boxing_mode)
    agent = build_agent(
        model=model_obj,
        fewshots=fewshots,
        model_settings=model_settings,
        boxing_mode=boxing_mode,
    )
    if print_tools:
        from tool_context_relay.agent.tool_definitions import print_tool_definitions

        print_tool_definitions(agent.tools, stream=sys.stderr)
    if hooks is None:
        hooks = RunHookHandler()
    result = Runner.run_sync(agent, prompt, max_turns=20, hooks=hooks, context=context)
    return result.final_output, context
