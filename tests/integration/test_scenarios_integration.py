from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tool_context_relay.main import run_once
from tool_context_relay.tools.tool_relay import is_resource_id

from tool_context_relay.testing.integration_hooks import (
    CaptureToolCalls,
    assert_tool_not_called,
    require_tool_call_result,
)
from tool_context_relay.testing.prompt_cases import (
    ToolCallExpectation,
)


pytestmark = pytest.mark.integration


INTERNAL_RESOLVE_TOOLS = (
    "internal_resource_read",
    "internal_resource_read_slice",
    "internal_resource_length",
)

OPENAI_COMPAT_URL = "http://127.0.0.1:1234/v1"


def _configure_provider_env(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    # Integration tests are expected to run with project-local `.env` and should not
    # require manual `export ...` in the shell.
    load_dotenv(verbose=True)

    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            pytest.fail(
                "OPENAI_API_KEY is missing/empty, but integration tests were requested. "
                "Set OPENAI_API_KEY to run the OpenAI integration cases."
            )
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        return

    if provider == "openai-compat":
        if not os.environ.get("OPENAI_COMPAT_API_KEY", "").strip() and not os.environ.get(
            "OPENAI_API_KEY", ""
        ).strip():
            pytest.fail(
                "OPENAI_COMPAT_API_KEY (or OPENAI_API_KEY) is missing/empty, but integration tests were requested. "
                "Set OPENAI_COMPAT_API_KEY for the OpenAI-compatible integration cases."
            )

        monkeypatch.setenv("OPENAI_BASE_URL", OPENAI_COMPAT_URL)
        monkeypatch.setenv("OPENAI_API_BASE", OPENAI_COMPAT_URL)
        return

    raise ValueError(f"unknown provider: {provider!r}")


def _assert_no_unnecessary_resolves(calls) -> None:
    for tool_name in INTERNAL_RESOLVE_TOOLS:
        assert_tool_not_called(calls, tool_name)


def _assert_internal_resolve_uses_opaque_reference(calls, opaque_reference: str) -> None:
    internal_tools = {"internal_resource_read", "internal_resource_read_slice", "internal_resource_length"}
    internal_calls = [call for call in calls if call.name in internal_tools]
    if not internal_calls:
        raise AssertionError("expected at least one internal_resource_* tool call to resolve transcript")

    for call in internal_calls:
        if "opaque_reference" not in call.arguments:
            raise AssertionError(f"expected {call.name} to include opaque_reference argument")
        if call.arguments["opaque_reference"] != opaque_reference:
            raise AssertionError(
                f"expected {call.name}.opaque_reference to equal {opaque_reference!r}, got {call.arguments['opaque_reference']!r}"
            )


def _assert_tool_calls_expectations(calls, expectations: list[ToolCallExpectation]) -> list[str]:
    expected_tool_names = [exp.tool_name for exp in expectations]
    expected_tool_name_set = set(expected_tool_names)

    actual_relevant = [call for call in calls if call.name in expected_tool_name_set]
    actual_tool_names = [call.name for call in actual_relevant]

    if actual_tool_names != expected_tool_names:
        raise AssertionError(
            "tool call sequence mismatch. "
            f"expected={expected_tool_names!r}, actual={actual_tool_names!r}"
        )

    opaque_ids_seen: list[str] = []
    for exp, call in zip(expectations, actual_relevant, strict=True):
        if exp.opaque_id_input:
            if not opaque_ids_seen:
                raise AssertionError(
                    f"expected {call.name} to use an opaque id as input, but no previous opaque id result exists"
                )
            uses_prev_opaque = any(value in opaque_ids_seen for value in call.arguments.values())
            if not uses_prev_opaque:
                raise AssertionError(
                    f"expected {call.name} to receive a previous opaque id as input; "
                    f"known_opaque_ids={opaque_ids_seen!r}, arguments={call.arguments!r}"
                )

        if exp.opaque_id_result:
            if not isinstance(call.result, str) or not call.result.strip():
                raise AssertionError(f"expected {call.name} to return a string result, got {call.result!r}")
            if not is_resource_id(call.result):
                raise AssertionError(f"expected {call.name} result to be an opaque id, got {call.result!r}")
            opaque_ids_seen.append(call.result)

    return opaque_ids_seen


def test_scenarios_integration(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    model: str,
    case_id: str,
    prompt: str,
    forbidden_tools: set[str],
    tool_calls: list[ToolCallExpectation],
    expect_internal_resolve: bool,
) -> None:
    _configure_provider_env(monkeypatch, provider)

    hooks = CaptureToolCalls()
    run_once(prompt=prompt, model=model, initial_kv={}, provider=provider, hooks=hooks)

    calls = hooks.tool_calls

    if not tool_calls and not forbidden_tools and not expect_internal_resolve:
        if calls:
            tool_names = sorted({call.name for call in calls})
            raise AssertionError(f"expected no tool calls, got {tool_names!r}")
        return

    for tool_name in forbidden_tools:
        assert_tool_not_called(calls, tool_name)

    opaque_ids_seen = _assert_tool_calls_expectations(calls, tool_calls)

    if expect_internal_resolve:
        transcript_ref = opaque_ids_seen[0] if opaque_ids_seen else require_tool_call_result(calls, "yt_transcribe")
        if not is_resource_id(transcript_ref):
            raise AssertionError(f"expected yt_transcribe to return an opaque reference, got {transcript_ref!r}")
        _assert_internal_resolve_uses_opaque_reference(calls, transcript_ref)
    else:
        _assert_no_unnecessary_resolves(calls)
