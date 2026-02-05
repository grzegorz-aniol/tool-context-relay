from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

from tool_context_relay.pretty import emit_info, emit_error
from tool_context_relay.openai_env import resolve_provider
from tool_context_relay.testing.prompt_cases import (
    PromptCase,
    expand_wildcard_pattern,
    load_prompt_case_from_file,
)
from tool_context_relay.testing.integration_hooks import (
    CaptureToolCalls,
    CapturedToolCall,
    assert_tool_not_called,
)
from tool_context_relay.tools.tool_relay import is_resource_id


@dataclass(frozen=True)
class FileRunResult:
    file_path: Path
    case_id: str | None
    status: str
    reasons: list[str]


def _has_env_endpoint_override() -> bool:
    return bool(os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE"))


def _parse_kv(pairs: list[str]) -> dict[str, str]:
    kv: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"invalid --set value (expected key=value): {pair}")
        key, value = pair.split("=", 1)
        if not key:
            raise ValueError(f"invalid --set value (empty key): {pair}")
        kv[key] = value
    return kv


def _normalize_model_for_agents(*, model: str) -> str:
    """Normalize model names before sending a request to an OpenAI(-compatible) server.

    The Agents SDK MultiProvider conventionally accepts model names like "openai/gpt-4.1".
    When talking directly to a server, we strip the leading "openai/" prefix so the
    actual model name is sent over the wire.
    """
    if model.startswith("openai/"):
        return model.removeprefix("openai/")
    return model


def _format_startup_config_line(
    *,
    provider_requested: str,
    provider_resolved: str,
    model_requested: str,
    model_effective: str,
    endpoint: str | None,
    temperature: float | None,
) -> str:
    parts: list[str] = ["Config used:"]

    if provider_requested != provider_resolved:
        parts.append(f"* provider={provider_resolved} (requested={provider_requested})")
    else:
        parts.append(f"* provider={provider_resolved}")

    if model_requested != model_effective:
        parts.append(f"* model={model_effective} (from={model_requested})")
    else:
        parts.append(f"* model={model_effective}")

    if endpoint:
        parts.append(f"* endpoint={endpoint}")

    if temperature is not None:
        parts.append(f"* temperature={temperature}")

    return "\n".join(parts)


def _assert_tool_calls_expectations(
    calls: list[CapturedToolCall],
    expectations: list[Any],
) -> list[str]:
    """Validate that tool calls match expectations."""
    from tool_context_relay.testing.prompt_cases import ToolCallExpectation

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


def _validate_case(
    case: PromptCase,
    calls: list[CapturedToolCall],
) -> list[str]:
    """Run all validations for a prompt case.

    Returns list of error messages. Empty list means all validations passed.
    """
    errors: list[str] = []

    # If the file opted into validation but didn't specify any expectations,
    # treat this as "no tool calls expected" (matches the old integration behavior).
    if not case.tool_calls and not case.forbidden_tools and not case.expect_internal_resolve:
        if calls:
            tool_names = sorted({call.name for call in calls})
            errors.append(f"expected no tool calls, got {tool_names!r}")
        return errors

    # Check forbidden tools
    for tool_name in case.forbidden_tools:
        try:
            assert_tool_not_called(calls, tool_name)
        except AssertionError as e:
            errors.append(str(e))

    # Check tool call expectations
    opaque_ids_seen: list[str] = []
    if case.tool_calls:
        try:
            opaque_ids_seen = _assert_tool_calls_expectations(calls, case.tool_calls)
        except AssertionError as e:
            errors.append(str(e))

    # Check internal resolve expectation
    if case.expect_internal_resolve:
        internal_tools = {"internal_resource_read", "internal_resource_read_slice", "internal_resource_length"}
        internal_calls = [call for call in calls if call.name in internal_tools]
        if not internal_calls:
            errors.append("expected at least one internal_resource_* tool call to resolve transcript")
            return errors

        transcript_ref: str | None = opaque_ids_seen[0] if opaque_ids_seen else None
        if transcript_ref is None:
            for call in calls:
                if call.name == "yt_transcribe" and isinstance(call.result, str) and call.result.strip():
                    transcript_ref = call.result
                    break

        if transcript_ref is None:
            errors.append("expected yt_transcribe to be called with a result, but could not find it")
            return errors
        if not is_resource_id(transcript_ref):
            errors.append(f"expected yt_transcribe to return an opaque reference, got {transcript_ref!r}")
            return errors

        for call in internal_calls:
            opaque_reference = call.arguments.get("opaque_reference")
            if opaque_reference != transcript_ref:
                errors.append(
                    f"expected {call.name}.opaque_reference to equal {transcript_ref!r}, got {opaque_reference!r}"
                )
    else:
        internal_tools = {"internal_resource_read", "internal_resource_read_slice", "internal_resource_length"}
        internal_calls = [call for call in calls if call.name in internal_tools]
        if internal_calls:
            errors.append("expected no internal_resource_* tool calls, but some were made")

    return errors


def _run_single_prompt(
    *,
    prompt: str,
    model: str,
    provider: str,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    capture_calls: bool = False,
) -> tuple[str, Any, CaptureToolCalls | None]:
    """Run a single prompt and optionally capture tool calls.

    Returns (output, context, capture_hooks) where capture_hooks is None if capture_calls is False.
    """
    from tool_context_relay.main import run_once
    from tool_context_relay.agent.handler import RunHookHandler

    if capture_calls:
        hooks = CaptureToolCalls(delegate=RunHookHandler(show_system_instruction=show_system_instruction))
    else:
        hooks = RunHookHandler(show_system_instruction=show_system_instruction)

    output, context = run_once(
        prompt=prompt,
        model=model,
        initial_kv=initial_kv,
        provider=provider,
        print_tools=print_tools,
        fewshots=fewshots,
        temperature=temperature,
        hooks=hooks,
    )

    return output, context, hooks if capture_calls else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool-context-relay")
    parser.add_argument(
        "prompt",
        nargs="?",
        help=(
            "User prompt to run once (the agent may call tools). "
            "For file/glob execution, use --file / --glob."
        ),
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="PATH",
        help="Run prompt(s) from a markdown file. Repeatable. If a file has YAML frontmatter, validation is enabled.",
    )
    parser.add_argument(
        "--glob",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Run prompt(s) from markdown files matched by a glob (e.g. 'prompt_cases/*.md'). Repeatable.",
    )
    parser.set_defaults(fewshots=True)
    fewshots_group = parser.add_mutually_exclusive_group()
    fewshots_group.add_argument(
        "--fewshots",
        action="store_true",
        help="Include extra few-shot examples in the agent instructions (default).",
    )
    fewshots_group.add_argument(
        "--no-fewshots",
        action="store_false",
        dest="fewshots",
        help="Disable extra few-shot examples in the agent instructions.",
    )
    parser.set_defaults(show_system_instruction=True)
    system_instruction_group = parser.add_mutually_exclusive_group()
    system_instruction_group.add_argument(
        "--show-system-instruction",
        action="store_true",
        help="Emit the agent system instruction (default).",
    )
    system_instruction_group.add_argument(
        "--no-show-system-instruction",
        action="store_false",
        dest="show_system_instruction",
        help="Do not emit the agent system instruction.",
    )
    parser.add_argument(
        "--color",
        default="auto",
        choices=["auto", "always", "never"],
        help="Color output mode (default: %(default)s).",
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help=(
            "Model name (default: %(default)s). "
            "If you pass an Agents-style prefix like 'openai/<model>', it will be stripped "
            "before sending the request."
        ),
    )
    parser.add_argument(
        "--temperature",
        default=None,
        type=float,
        metavar="FLOAT",
        help=(
            "Sampling temperature for non-reasoning models (e.g. 0.1). "
            "If omitted, temperature is not set. "
            "For reasoning models, this flag is ignored."
        ),
    )
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "openai", "openai-compat"],
        help=(
            "Which API provider to use for auth/env mapping (default: %(default)s). "
            "'openai-compat' requires --endpoint or OPENAI_BASE_URL/OPENAI_API_BASE."
        ),
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        metavar="URL",
        help=(
            "OpenAI-compatible API base URL (e.g. http://localhost:11434/v1). "
            "Overrides OPENAI_BASE_URL / OPENAI_API_BASE for this run."
        ),
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Seed initial context (repeatable).",
    )
    parser.add_argument(
        "--dump-context",
        action="store_true",
        help="Print final context as JSON to stderr.",
    )
    parser.add_argument(
        "--print-tools",
        action="store_true",
        help="Print tool definitions (name/description/arg schema) to stderr before running the agent.",
    )
    return parser


def _is_reasoning_model(*, model: str) -> bool:
    """Heuristic: treat 'gpt-5*' and 'o*' model IDs as reasoning models.

    This mirrors patterns used in other projects in this workspace and avoids
    sending unsupported sampling params (e.g., temperature) to reasoning models.
    """
    normalized = model.strip().lower()
    if not normalized:
        return False
    if normalized.startswith("gpt-5"):
        return True
    if normalized.startswith("o1") or normalized.startswith("o3") or normalized.startswith("o4"):
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Propagate to the pretty emitter, and transitively to tool hooks.
    os.environ["TOOL_CONTEXT_RELAY_COLOR"] = args.color

    provider = args.provider

    if args.endpoint is not None:
        endpoint = args.endpoint.strip()
        if not endpoint:
            print("Endpoint must not be empty.", file=sys.stderr)
            return 2
        os.environ["OPENAI_BASE_URL"] = endpoint
        os.environ["OPENAI_API_BASE"] = endpoint

    has_endpoint_override = _has_env_endpoint_override()
    if provider == "openai-compat" and not has_endpoint_override:
        print(
            "Provider 'openai-compat' requires an endpoint override via --endpoint or OPENAI_BASE_URL/OPENAI_API_BASE.",
            file=sys.stderr,
        )
        return 2
    if provider == "openai" and has_endpoint_override:
        print(
            "Provider 'openai' cannot be used with an endpoint override (--endpoint / OPENAI_BASE_URL / OPENAI_API_BASE).",
            file=sys.stderr,
        )
        return 2

    try:
        initial_kv = _parse_kv(args.set)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    file_args: list[str] = [str(x) for x in (args.file or []) if str(x).strip()]
    glob_args: list[str] = [str(x) for x in (args.glob or []) if str(x).strip()]
    has_file_mode = bool(file_args or glob_args)

    prompt_arg = (args.prompt or "").strip()
    if has_file_mode and prompt_arg:
        print("Use either a literal prompt argument OR --file/--glob (not both).", file=sys.stderr)
        return 2
    if not has_file_mode and not prompt_arg:
        print("Prompt must not be empty.", file=sys.stderr)
        return 2

    temperature: float | None = args.temperature
    if temperature is not None:
        if not math.isfinite(temperature):
            print("Temperature must be a finite number.", file=sys.stderr)
            return 2
        if temperature < 0.0 or temperature > 2.0:
            print("Temperature must be between 0.0 and 2.0.", file=sys.stderr)
            return 2

    model = _normalize_model_for_agents(model=args.model)
    if temperature is not None and _is_reasoning_model(model=model):
        emit_info(
            f"Ignoring --temperature={temperature} because model '{model}' looks like a reasoning model.",
            stream=sys.stdout,
        )
        temperature = None
    endpoint_to_print = None
    if has_endpoint_override:
        endpoint_to_print = (os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or "").strip() or None

    config_line = _format_startup_config_line(
        provider_requested=provider,
        provider_resolved=resolve_provider(provider),
        model_requested=args.model,
        model_effective=model,
        endpoint=endpoint_to_print,
        temperature=temperature,
    )
    emit_info(config_line, stream=sys.stdout)

    # Run prompts
    try:
        if has_file_mode:
            # Running from file(s)
            files: list[Path] = []
            for value in file_args:
                path = Path(value)
                if not path.exists() or not path.is_file():
                    print(f"--file path not found or not a file: {value}", file=sys.stderr)
                    return 2
                files.append(path)
            for pattern in glob_args:
                matched = expand_wildcard_pattern(pattern)
                if not matched:
                    print(f"--glob matched no files: {pattern}", file=sys.stderr)
                    return 2
                files.extend(matched)

            # De-dup while preserving deterministic order.
            unique: dict[Path, None] = {}
            for p in files:
                unique[p] = None
            files = list(unique.keys())

            return _run_from_files(
                files=files,
                model=model,
                provider=provider,
                initial_kv=initial_kv,
                print_tools=args.print_tools,
                fewshots=args.fewshots,
                show_system_instruction=args.show_system_instruction,
                temperature=temperature,
                dump_context=args.dump_context,
            )
        else:
            # Running literal prompt
            return _run_literal_prompt(
                prompt=prompt_arg,
                model=model,
                provider=provider,
                initial_kv=initial_kv,
                print_tools=args.print_tools,
                fewshots=args.fewshots,
                show_system_instruction=args.show_system_instruction,
                temperature=temperature,
                dump_context=args.dump_context,
            )
    except ModuleNotFoundError as e:
        if e.name == "agents":
            print(
                "Missing dependency: openai-agents. Install deps then re-run.",
                file=sys.stderr,
            )
            return 1
        raise


def _run_literal_prompt(
    *,
    prompt: str,
    model: str,
    provider: str,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    dump_context: bool,
) -> int:
    """Run a literal prompt (no validation)."""
    from tool_context_relay.agent.handler import RunHookHandler
    from tool_context_relay.main import run_once

    hooks = RunHookHandler(show_system_instruction=show_system_instruction)
    output, context = run_once(
        prompt=prompt,
        model=model,
        initial_kv=initial_kv,
        provider=provider,
        print_tools=print_tools,
        fewshots=fewshots,
        temperature=temperature,
        hooks=hooks,
    )

    if dump_context:
        print(json.dumps(context.kv, ensure_ascii=False, sort_keys=True), file=sys.stdout)

    emit_info(
        dedent(f"""
        Session summary:
        * tool_calls={hooks.tool_calls},
        * tool_results_with_resource_id={hooks.tool_results_with_resource_id},
        * tool_calls_with_resource_id_args={hooks.tool_calls_with_resource_id_args}
        """).strip(),
        stream=sys.stdout,
    )
    return 0


def _run_from_files(
    *,
    files: list[Path],
    model: str,
    provider: str,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    dump_context: bool,
) -> int:
    """Run prompts from one or more files.

    If file has frontmatter, validate the output against expectations.
    Returns 0 if all validations pass, 1 if any fail.
    """
    from tool_context_relay.main import run_once

    all_passed = True
    total_files = len(files)
    results: list[FileRunResult] = []

    for idx, file_path in enumerate(files, 1):
        emit_info(f"\n[{idx}/{total_files}] Running: {file_path}", stream=sys.stdout)

        try:
            case, prompt = load_prompt_case_from_file(file_path)
        except (ValueError, TypeError) as e:
            emit_error(f"Failed to load {file_path}: {e}", stream=sys.stderr)
            all_passed = False
            results.append(
                FileRunResult(
                    file_path=file_path,
                    case_id=None,
                    status="error",
                    reasons=[f"load: {e}"],
                )
            )
            continue

        # Run the prompt with tool call capture
        from tool_context_relay.agent.handler import RunHookHandler

        hooks = CaptureToolCalls(delegate=RunHookHandler(show_system_instruction=show_system_instruction))
        try:
            output, context = run_once(
                prompt=prompt,
                model=model,
                initial_kv=initial_kv,
                provider=provider,
                print_tools=print_tools,
                fewshots=fewshots,
                temperature=temperature,
                hooks=hooks,
            )
        except Exception as e:
            emit_error(f"Error running {file_path}: {e}", stream=sys.stderr)
            all_passed = False
            results.append(
                FileRunResult(
                    file_path=file_path,
                    case_id=case.case_id if case is not None else None,
                    status="error",
                    reasons=[f"run: {e}"],
                )
            )
            continue

        if dump_context:
            print(json.dumps(context.kv, ensure_ascii=False, sort_keys=True), file=sys.stdout)

        # Validate if frontmatter exists
        if case is not None:
            errors = _validate_case(case, hooks.tool_calls)
            if errors:
                all_passed = False
                emit_error(f"Validation FAILED for {file_path}:", stream=sys.stderr)
                for error in errors:
                    emit_error(f"  - {error}", stream=sys.stderr)
                results.append(
                    FileRunResult(
                        file_path=file_path,
                        case_id=case.case_id,
                        status="failed",
                        reasons=errors,
                    )
                )
            else:
                emit_info(f"  ✓ Validation PASSED for {case.case_id}", stream=sys.stdout)
                results.append(
                    FileRunResult(
                        file_path=file_path,
                        case_id=case.case_id,
                        status="passed",
                        reasons=[],
                    )
                )
        else:
            emit_info(f"  (no validation - no frontmatter)", stream=sys.stdout)
            results.append(
                FileRunResult(
                    file_path=file_path,
                    case_id=None,
                    status="no_validation",
                    reasons=[],
                )
            )

        # Print summary
        emit_info(
            f"  tool_calls={len(hooks.tool_calls)}, "
            f"results_with_resource_id={sum(1 for c in hooks.tool_calls if c.result and is_resource_id(c.result))}",
            stream=sys.stdout,
        )

    emit_info(f"\n{'=' * 50}", stream=sys.stdout)
    emit_info("Run summary:", stream=sys.stdout)
    for result in results:
        label = result.case_id or str(result.file_path)
        if result.case_id:
            label = f"{label} ({result.file_path})"

        if result.status == "passed":
            emit_info(f"  ✓ {label}", stream=sys.stdout)
        elif result.status == "no_validation":
            emit_info(f"  • {label} (no validation)", stream=sys.stdout)
        elif result.status == "failed":
            emit_error(f"  ✗ {label}", stream=sys.stderr)
            for reason in result.reasons:
                emit_error(f"    - {reason}", stream=sys.stderr)
        else:
            emit_error(f"  ✗ {label} ({result.status})", stream=sys.stderr)
            for reason in result.reasons:
                emit_error(f"    - {reason}", stream=sys.stderr)

    if all_passed:
        emit_info(f"All {total_files} file(s) passed.", stream=sys.stdout)
        return 0
    else:
        emit_error("Some validations failed.", stream=sys.stderr)
        return 1
