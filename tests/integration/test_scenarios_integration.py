from __future__ import annotations

import os
import sys
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
    for tool_name in ("internal_resource_read", "internal_resource_read_slice", "internal_resource_length"):
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
    ("provider", "prompt", "expect_internal_resolve", "expect_deep_check", "expect_drive_saves"),
    [
        ("openai", PROMPT_1, False, True, False),
        ("openai", PROMPT_2, False, False, True),
        ("openai", PROMPT_3, True, True, False),
        ("openai", PROMPT_4, False, True, True),
        ("openai-compat", PROMPT_1, False, True, False),
        ("openai-compat", PROMPT_2, False, False, True),
        ("openai-compat", PROMPT_3, True, True, False),
        ("openai-compat", PROMPT_4, False, True, True),
    ],
    ids=[
        "openai-case1",
        "openai-case2",
        "openai-case3",
        "openai-case4",
        "openai-compat-case1",
        "openai-compat-case2",
        "openai-compat-case3",
        "openai-compat-case4",
    ],
)
def test_scenarios_integration(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    prompt: str,
    expect_internal_resolve: bool,
    expect_deep_check: bool,
    expect_drive_saves: bool,
) -> None:
    model = _configure_provider_env(monkeypatch, provider)

    hooks = CaptureToolCalls()
    run_once(prompt=prompt, model=model, initial_kv={}, provider=provider, hooks=hooks)

    calls = hooks.tool_calls
    assert_tool_called(calls, "yt_transcribe")
    assert_tool_called(calls, "deep_check")

    transcript_ref = require_tool_call_result(calls, "yt_transcribe")
    if not is_resource_id(transcript_ref):
        raise AssertionError(f"expected yt_transcribe to return an opaque reference, got {transcript_ref!r}")

    if expect_deep_check:
        assert_opaque_pass_through(
            calls=calls,
            opaque_reference=transcript_ref,
            tool_name="deep_check",
            argument_name="text",
        )

    if expect_drive_saves:
        assert_tool_called(calls, "google_drive_write_file")
        assert_opaque_pass_through(
            calls=calls,
            opaque_reference=transcript_ref,
            tool_name="google_drive_write_file",
            argument_name="file_content",
            argument_filter={"file_name": "transcript.txt"},
        )
        _assert_no_unnecessary_resolves(calls)

    if expect_internal_resolve:
        _assert_internal_resolve_uses_opaque_reference(calls, transcript_ref)

    if not expect_drive_saves and not expect_deep_check and not expect_internal_resolve:
        _assert_no_unnecessary_resolves(calls)
