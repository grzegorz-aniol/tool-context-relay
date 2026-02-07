from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import re
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, TextIO

from dotenv import load_dotenv

from tool_context_relay.pretty import emit_info, emit_error
from tool_context_relay.openai_env import ProfileConfig, load_profile
from tool_context_relay.temperature import ensure_valid_temperature
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
from tool_context_relay.boxing import BoxingMode
from tool_context_relay.tools.tool_relay import is_resource_id


@dataclass(frozen=True)
class FileRunResult:
    file_path: Path
    case_id: str | None
    status: str
    reasons: list[str]



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


def _resolve_profile_name(requested: str | None) -> str:
    requested_value = (requested or "").strip()
    if requested_value:
        return requested_value
    env_value = (os.environ.get("TOOL_CONTEXT_RELAY_PROFILE") or "").strip()
    if env_value:
        return env_value
    return "openai"


def _format_startup_config_line(
    *,
    profile: str,
    provider: str,
    model_requested: str | None,
    model_effective: str,
    endpoint: str | None,
    temperature: float | None,
    boxing_mode: BoxingMode,
    is_fewshot: bool,
) -> str:
    parts: list[str] = ["Config used:"]

    parts.append(f"* profile={profile}")
    parts.append(f"* provider={provider}")

    if model_requested and model_requested != model_effective:
        parts.append(f"* model={model_effective} (requested={model_requested})")
    else:
        parts.append(f"* model={model_effective}")

    if endpoint:
        parts.append(f"* endpoint={endpoint}")

    if temperature is not None:
        parts.append(f"* temperature={temperature}")
    parts.append(f"* boxing={boxing_mode}")
    parts.append(f"* few-shots={'enabled' if is_fewshot else 'disabled'}")

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
    profile: str,
    profile_config: ProfileConfig,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    boxing_mode: BoxingMode,
    max_retries: int | None = None,
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
        profile=profile,
        profile_config=profile_config,
        print_tools=print_tools,
        fewshots=fewshots,
        temperature=temperature,
        boxing_mode=boxing_mode,
        hooks=hooks,
        max_retries=max_retries,
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
        help="Run prompt(s) from markdown files matched by a glob (e.g. 'prompts/*.md'). Repeatable.",
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
        default=None,
        help=(
            "Model name (optional). "
            "If omitted, the profile's default model (or gpt-4.1-mini) is used. "
            "Agents-style prefixes like 'openai/<model>' are stripped."
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
        "--max-retries",
        type=int,
        default=None,
        help="Max retries for OpenAI requests (passed to AsyncOpenAI).",
    )
    parser.add_argument(
        "--boxing",
        default="opaque",
        choices=["opaque", "json"],
        help="Boxing strategy for large tool outputs (default: %(default)s).",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help=(
            "Profile name (default from TOOL_CONTEXT_RELAY_PROFILE or 'openai'). "
            "Profiles map to <PREFIX>_API_KEY, <PREFIX>_MODEL, and so on."
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

    load_dotenv(verbose=True)

    # Propagate to the pretty emitter, and transitively to tool hooks.
    os.environ["TOOL_CONTEXT_RELAY_COLOR"] = args.color

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

    profile = _resolve_profile_name(args.profile)
    try:
        profile_config = load_profile(profile)
    except (ValueError, RuntimeError) as e:
        print(f"Invalid profile '{profile}': {e}", file=sys.stderr)
        return 2

    if profile_config.api_key is None:
        print(
            f"Profile '{profile}' must set {profile_config.prefix}_API_KEY (or another matching key).",
            file=sys.stderr,
        )
        return 2

    model_requested: str | None = (args.model or "").strip() or None
    model_source = model_requested or profile_config.default_model or "gpt-4.1-mini"
    if args.temperature is not None:
        try:
            temperature = ensure_valid_temperature(args.temperature)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
    else:
        temperature = profile_config.temperature
    model = _normalize_model_for_agents(model=model_source)

    if temperature is not None and _is_reasoning_model(model=model):
        emit_info(
            f"Ignoring temperature={temperature} because model '{model}' looks like a reasoning model.",
            stream=sys.stdout,
        )
        temperature = None
    max_retries: int | None = args.max_retries
    if max_retries is not None and max_retries < 0:
        print("Max retries must be >= 0.", file=sys.stderr)
        return 2
    config_line = _format_startup_config_line(
        profile=profile,
        provider=profile_config.provider,
        model_requested=model_requested,
        model_effective=model,
        endpoint=profile_config.endpoint,
        temperature=temperature,
        boxing_mode=args.boxing,
        is_fewshot=args.fewshots,
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
                profile=profile,
                profile_config=profile_config,
                initial_kv=initial_kv,
                print_tools=args.print_tools,
                fewshots=args.fewshots,
                show_system_instruction=args.show_system_instruction,
                temperature=temperature,
                boxing_mode=args.boxing,
                max_retries=max_retries,
                dump_context=args.dump_context,
            )
        else:
            # Running literal prompt
            return _run_literal_prompt(
                prompt=prompt_arg,
                model=model,
                profile=profile,
                profile_config=profile_config,
                initial_kv=initial_kv,
                print_tools=args.print_tools,
                fewshots=args.fewshots,
                show_system_instruction=args.show_system_instruction,
                temperature=temperature,
                boxing_mode=args.boxing,
                max_retries=max_retries,
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
    profile: str,
    profile_config: ProfileConfig,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    boxing_mode: BoxingMode,
    max_retries: int | None = None,
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
        profile=profile,
        profile_config=profile_config,
        print_tools=print_tools,
        fewshots=fewshots,
        temperature=temperature,
        boxing_mode=boxing_mode,
        hooks=hooks,
        max_retries=max_retries,
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
    profile: str,
    profile_config: ProfileConfig,
    initial_kv: dict[str, str],
    print_tools: bool,
    fewshots: bool,
    show_system_instruction: bool,
    temperature: float | None,
    boxing_mode: BoxingMode,
    max_retries: int | None = None,
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
                profile=profile,
                profile_config=profile_config,
                print_tools=print_tools,
                fewshots=fewshots,
                temperature=temperature,
                boxing_mode=boxing_mode,
                hooks=hooks,
                max_retries=max_retries,
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

    sys.stdout.flush()
    sys.stderr.flush()
    print(file=sys.stderr)
    print("\x1b[0m", file=sys.stderr, end="")
    _print_validation_summary_table(
        model=model,
        fewshots=fewshots,
        results=results,
        stream=sys.stderr,
    )

    if all_passed:
        print(f"All {total_files} file(s) passed.", file=sys.stdout)
        return 0
    print("Some validations failed.", file=sys.stderr)
    return 1


def _reason_for_result(result: FileRunResult) -> str:
    if result.reasons:
        cleaned = (
            _truncate_reason_clause(_strip_tool_call_arguments(reason))
            for reason in result.reasons
        )
        return "; ".join(cleaned)
    if result.status == "passed":
        return ""
    if result.status == "no_validation":
        return "?"
    return result.status


def _sanitize_table_cell(value: str) -> str:
    sanitized = value.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return sanitized.strip()


def _strip_tool_call_arguments(value: str) -> str:
    return re.sub(r",? arguments=.*$", "", value, flags=re.DOTALL)


def _truncate_reason_clause(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    clause, _, _ = trimmed.partition(";")
    return clause.strip()


def _print_validation_summary_table(
    *,
    model: str,
    fewshots: bool,
    results: list[FileRunResult],
    stream: TextIO | None = None,
) -> None:
    resolved_stream = stream or sys.stdout
    fewshot_symbol = "✔" if fewshots else "-"
    sanitized_model = _sanitize_table_cell(model)
    lines: list[str] = []
    lines.append("| Model | Prompt Id | Few-shot | Resolve success | Reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for result in results:
        prompt_id = result.case_id or str(result.file_path)
        reason = _reason_for_result(result)
        sanitized_prompt_id = _sanitize_table_cell(prompt_id)
        sanitized_reason = _sanitize_table_cell(reason)
        resolve_symbol = "✅" if result.status == "passed" else "❌"
        lines.append(
            f"| {sanitized_model} | {sanitized_prompt_id} | {fewshot_symbol} | {resolve_symbol} | {sanitized_reason} |"
        )

    print("\n".join(lines), file=resolved_stream)
