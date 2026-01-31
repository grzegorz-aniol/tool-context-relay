from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tool_context_relay.main import run_once
from tool_context_relay.tools.tool_relay import is_resource_id

from tool_context_relay.testing.integration_hooks import (
    CaptureToolCalls,
    assert_opaque_pass_through,
    assert_tool_called,
    assert_tool_not_called,
    require_tool_call_result,
)


pytestmark = pytest.mark.integration


INTERNAL_RESOLVE_TOOLS = (
    "internal_resource_read",
    "internal_resource_read_slice",
    "internal_resource_length",
)


@dataclass(frozen=True)
class OpaquePassThroughExpectation:
    source_tool_name: str
    destination_tool_name: str
    destination_argument_name: str
    destination_argument_filter: dict[str, str] | None = None


PROMPT_1 = dedent(
    """
    Generate transcript of YT video with video_id='123' and then pass it for deep analysis.
    """
).strip()

PROMPT_2 = dedent(
    """
    Generate transcript of YT video with video_id='123' and save it to a file at google drive named 'transcript.txt'.
    """
).strip()

PROMPT_3 = dedent(
    """
    Generate transcript of YT video with video_id='123' and then pass it for deep analysis.
    Then, let me know what number is included in the end of the transcript.
    """
).strip()

PROMPT_4 = dedent(
    """
    Generate transcript of YT video with video_id='123' and then pass it for deep analysis. 
    Then, save both the transcript and the analysis to files at google drive named 
    'transcript.txt' and 'analysis.txt' respectively.
    """
).strip()

OPENAI_COMPAT_URL = "http://127.0.0.1:1234/v1"
OPENAI_COMPAT_MODEL = (
    "speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"
)


def _configure_provider_env(monkeypatch: pytest.MonkeyPatch, provider: str) -> str:
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
        return os.environ.get("TCR_INTEGRATION_OPENAI_MODEL", "gpt-4.1-mini")

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
        return OPENAI_COMPAT_MODEL

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


@pytest.mark.parametrize(
    (
        "provider",
        "prompt",
        "required_tools",
        "forbidden_tools",
        "opaque_pass_through_expectations",
        "expect_internal_resolve",
    ),
    [
        (provider, *scenario)
        for provider in ("openai", "openai-compat")
        for scenario in [
            (
                PROMPT_1,
                {"yt_transcribe", "deep_check"},
                {"google_drive_write_file"},
                [
                    OpaquePassThroughExpectation(
                        source_tool_name="yt_transcribe",
                        destination_tool_name="deep_check",
                        destination_argument_name="text",
                    ),
                ],
                False,
            ),
            (
                PROMPT_2,
                {"yt_transcribe", "google_drive_write_file"},
                {"deep_check"},
                [
                    OpaquePassThroughExpectation(
                        source_tool_name="yt_transcribe",
                        destination_tool_name="google_drive_write_file",
                        destination_argument_name="file_content",
                        destination_argument_filter={"file_name": "transcript.txt"},
                    ),
                ],
                False,
            ),
            (
                PROMPT_3,
                {"yt_transcribe", "deep_check"},
                {"google_drive_write_file"},
                [
                    OpaquePassThroughExpectation(
                        source_tool_name="yt_transcribe",
                        destination_tool_name="deep_check",
                        destination_argument_name="text",
                    ),
                ],
                True,
            ),
            (
                PROMPT_4,
                {"yt_transcribe", "deep_check", "google_drive_write_file"},
                set(),
                [
                    OpaquePassThroughExpectation(
                        source_tool_name="yt_transcribe",
                        destination_tool_name="deep_check",
                        destination_argument_name="text",
                    ),
                    OpaquePassThroughExpectation(
                        source_tool_name="yt_transcribe",
                        destination_tool_name="google_drive_write_file",
                        destination_argument_name="file_content",
                        destination_argument_filter={"file_name": "transcript.txt"},
                    ),
                ],
                False,
            ),
        ]
    ],
    ids=[
        f"{provider}-case{case_num}"
        for provider in ("openai", "openai-compat")
        for case_num in range(1, 5)
    ],
)
def test_scenarios_integration(
    pytestconfig: pytest.Config,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    prompt: str,
    required_tools: set[str],
    forbidden_tools: set[str],
    opaque_pass_through_expectations: list[OpaquePassThroughExpectation],
    expect_internal_resolve: bool,
) -> None:
    selected_provider = pytestconfig.getoption("--provider")
    if selected_provider != "all" and provider != selected_provider:
        pytest.skip(f"--provider={selected_provider!r} excludes provider={provider!r}")

    model = _configure_provider_env(monkeypatch, provider)

    hooks = CaptureToolCalls()
    run_once(prompt=prompt, model=model, initial_kv={}, provider=provider, hooks=hooks)

    calls = hooks.tool_calls

    if not required_tools and not forbidden_tools and not opaque_pass_through_expectations and not expect_internal_resolve:
        if calls:
            tool_names = sorted({call.name for call in calls})
            raise AssertionError(f"expected no tool calls, got {tool_names!r}")
        return

    for tool_name in required_tools:
        assert_tool_called(calls, tool_name)

    for tool_name in forbidden_tools:
        assert_tool_not_called(calls, tool_name)

    transcript_ref: str | None = None
    needs_transcript_ref = (
        "yt_transcribe" in required_tools
        or any(exp.source_tool_name == "yt_transcribe" for exp in opaque_pass_through_expectations)
        or expect_internal_resolve
    )
    if needs_transcript_ref:
        transcript_ref = require_tool_call_result(calls, "yt_transcribe")
        if not is_resource_id(transcript_ref):
            raise AssertionError(
                f"expected yt_transcribe to return an opaque reference, got {transcript_ref!r}"
            )

    for exp in opaque_pass_through_expectations:
        opaque_reference = require_tool_call_result(calls, exp.source_tool_name)
        assert_opaque_pass_through(
            calls=calls,
            opaque_reference=opaque_reference,
            tool_name=exp.destination_tool_name,
            argument_name=exp.destination_argument_name,
            argument_filter=exp.destination_argument_filter,
        )

    if expect_internal_resolve:
        if transcript_ref is None:
            transcript_ref = require_tool_call_result(calls, "yt_transcribe")
        _assert_internal_resolve_uses_opaque_reference(calls, transcript_ref)
    else:
        _assert_no_unnecessary_resolves(calls)
