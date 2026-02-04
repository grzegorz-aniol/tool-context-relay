from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tool_context_relay.testing.prompt_cases import PromptCase, load_prompt_cases


DEFAULT_OPENAI_COMPAT_MODEL = (
    "speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"
)


def configured_models_for_provider(provider: str, env: Mapping[str, str]) -> list[str]:
    if provider == "openai":
        raw = (env.get("TCR_INTEGRATION_OPENAI_MODELS", "") or "").strip()
        if raw:
            return [item.strip() for item in raw.split(",") if item.strip()]
        return [env.get("TCR_INTEGRATION_OPENAI_MODEL", "gpt-4.1-mini")]

    if provider == "openai-compat":
        raw = (env.get("TCR_INTEGRATION_OPENAI_COMPAT_MODELS", "") or "").strip()
        if raw:
            return [item.strip() for item in raw.split(",") if item.strip()]
        return [DEFAULT_OPENAI_COMPAT_MODEL]

    raise ValueError(f"unknown provider: {provider!r}")


def normalize_case_selector(value: str) -> str:
    value = value.strip()
    value = Path(value).name
    value = value.removesuffix(".md").removesuffix(".txt")
    if value.isdigit():
        return value
    return value.removeprefix("case")


def select_cases(cases: list[PromptCase], prompt_case_options: list[str]) -> list[PromptCase]:
    if not prompt_case_options:
        return cases

    selected_case_ids = {normalize_case_selector(item) for item in prompt_case_options if item.strip()}
    return [case for case in cases if case.case_id.removeprefix("case") in selected_case_ids]


def build_integration_matrix(
    *,
    cases_dir: Path,
    provider_option: str,
    model_options: list[str],
    prompt_case_options: list[str],
    env: Mapping[str, str],
) -> tuple[list[tuple], list[str]]:
    cases = load_prompt_cases(cases_dir)
    cases = select_cases(cases, prompt_case_options)

    providers = ["openai", "openai-compat"] if provider_option == "all" else [provider_option]

    selected_models = [m.strip() for m in model_options if m.strip()]
    override_models = selected_models and "all" not in selected_models

    params: list[tuple] = []
    ids: list[str] = []
    for provider in providers:
        models = selected_models if override_models else configured_models_for_provider(provider, env)
        for model in models:
            for case in cases:
                params.append(
                    (
                        provider,
                        model,
                        case.case_id,
                        case.prompt,
                        case.forbidden_tools,
                        case.tool_calls,
                        case.expect_internal_resolve,
                    )
                )
                ids.append(f"{provider}-{model}-{case.case_id}")

    return params, ids

