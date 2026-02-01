from __future__ import annotations

import argparse
import json
import os
import sys

from tool_context_relay.openai_env import resolve_provider


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
) -> str:
    parts: list[str] = ["tool-context-relay config:"]

    if provider_requested != provider_resolved:
        parts.append(f"provider={provider_resolved} (requested={provider_requested})")
    else:
        parts.append(f"provider={provider_resolved}")

    if model_requested != model_effective:
        parts.append(f"model={model_effective} (from={model_requested})")
    else:
        parts.append(f"model={model_effective}")

    if endpoint:
        parts.append(f"endpoint={endpoint}")

    return " ".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool-context-relay")
    parser.add_argument(
        "prompt",
        help="User prompt to run once (the agent may call tools).",
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

    if not args.prompt.strip():
        print("Prompt must not be empty.", file=sys.stderr)
        return 2

    try:
        from tool_context_relay.main import run_once

        model = _normalize_model_for_agents(model=args.model)
        endpoint_to_print = None
        if has_endpoint_override:
            endpoint_to_print = (os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or "").strip() or None

        config_line = _format_startup_config_line(
            provider_requested=provider,
            provider_resolved=resolve_provider(provider),
            model_requested=args.model,
            model_effective=model,
            endpoint=endpoint_to_print,
        )
        print(config_line, file=sys.stderr)

        output, context = run_once(
            prompt=args.prompt,
            model=model,
            initial_kv=initial_kv,
            provider=provider,
            print_tools=args.print_tools,
            fewshots=args.fewshots,
        )
    except ModuleNotFoundError as e:
        if e.name == "agents":
            print(
                "Missing dependency: openai-agents. Install deps then re-run.",
                file=sys.stderr,
            )
            return 1
        raise

    if args.dump_context:
        print(json.dumps(context.kv, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 0
