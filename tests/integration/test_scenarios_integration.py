from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tool_context_relay.main import run_once
from tool_context_relay.openai_env import load_profile
from tool_context_relay.cli import _assert_tool_calls_expectations
from tool_context_relay.testing.integration_hooks import (
    CaptureToolCalls,
    assert_tool_not_called,
)
from tool_context_relay.testing.prompt_cases import (
    ToolCallExpectation,
)


pytestmark = pytest.mark.integration



def _configure_profile_env(monkeypatch: pytest.MonkeyPatch, profile: str) -> None:
    load_dotenv(verbose=True)

    if profile == "openai":
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    try:
        load_profile(profile)
    except Exception as exc:
        pytest.fail(f"profile '{profile}' is not configured properly: {exc}")


def test_scenarios_integration(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    model: str,
    case_id: str,
    prompt: str,
    forbidden_tools: set[str],
    tool_calls: list[ToolCallExpectation],
) -> None:
    _configure_profile_env(monkeypatch, profile)

    hooks = CaptureToolCalls()
    run_once(prompt=prompt, model=model, profile=profile, hooks=hooks)

    calls = hooks.tool_calls

    if not tool_calls and not forbidden_tools:
        if calls:
            tool_names = sorted({call.name for call in calls})
            raise AssertionError(f"expected no tool calls, got {tool_names!r}")
        return

    for tool_name in forbidden_tools:
        assert_tool_not_called(calls, tool_name)

    _assert_tool_calls_expectations(calls, tool_calls)
