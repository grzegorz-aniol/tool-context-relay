from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from tool_context_relay.testing.prompt_cases import PromptCase, load_prompt_cases


PROFILE_DEFAULT_MODELS: dict[str, list[str]] = {
    "OPENAI": ["gpt-4.1-mini"],
    "BIELIK": [
        "speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"
    ],
    "QWEN": ["Qwen/Qwen3-8B-GGUF:Q8_0"],
}


AVAILABLE_PROFILES: list[str] = ["openai", "bielik", "qwen"]


def _normalize_profile_key(profile: str) -> str:
    value = profile.strip()
    if not value:
        raise ValueError("profile name must not be empty")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not normalized:
        raise ValueError("profile name must contain letters or digits")
    return normalized.upper()


def configured_models_for_profile(profile: str, env: Mapping[str, str]) -> list[str]:
    normalized = _normalize_profile_key(profile)
    models_key = f"TCR_INTEGRATION_{normalized}_MODELS"
    models_raw = (env.get(models_key, "") or "").strip()
    if models_raw:
        return [item.strip() for item in models_raw.split(",") if item.strip()]

    single_key = f"TCR_INTEGRATION_{normalized}_MODEL"
    single_raw = (env.get(single_key, "") or "").strip()
    if single_raw:
        return [single_raw]

    return PROFILE_DEFAULT_MODELS.get(normalized, ["gpt-4.1-mini"])


def normalize_case_selector(value: str) -> str:
    value = value.strip()
    value = Path(value).name
    value = value.removeprefix(".md").removeprefix(".txt")
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
    profile_option: str,
    model_options: list[str],
    prompt_case_options: list[str],
    env: Mapping[str, str],
) -> tuple[list[tuple], list[str]]:
    cases = load_prompt_cases(cases_dir)
    cases = select_cases(cases, prompt_case_options)

    profiles = AVAILABLE_PROFILES if profile_option == "all" else [profile_option]

    selected_models = [m.strip() for m in model_options if m.strip()]
    override_models = selected_models and "all" not in selected_models

    params: list[tuple] = []
    ids: list[str] = []
    for profile in profiles:
        models = selected_models if override_models else configured_models_for_profile(profile, env)
        for model in models:
            for case in cases:
                params.append(
                    (
                        profile,
                        model,
                        case.case_id,
                        case.prompt,
                        case.forbidden_tools,
                        case.tool_calls,
                        case.expect_internal_resolve,
                    )
                )
                ids.append(f"{profile}-{model}-{case.case_id}")

    return params, ids
