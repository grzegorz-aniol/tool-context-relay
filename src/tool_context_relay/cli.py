from __future__ import annotations

import argparse
import json
import os
import sys

from tool_context_relay.main import run_once


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool-context-relay")
    parser.add_argument(
        "prompt",
        help="User prompt to run once (the agent may call tools).",
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
        help="Model name (default: %(default)s).",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Propagate to the pretty emitter, and transitively to tool hooks.
    os.environ["TOOL_CONTEXT_RELAY_COLOR"] = args.color

    try:
        initial_kv = _parse_kv(args.set)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if not args.prompt.strip():
        print("Prompt must not be empty.", file=sys.stderr)
        return 2

    try:
        output, context = run_once(prompt=args.prompt, model=args.model, initial_kv=initial_kv)
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
