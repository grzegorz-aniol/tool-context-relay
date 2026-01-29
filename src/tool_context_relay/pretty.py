from __future__ import annotations

import os
import sys
import textwrap

_ANSI_RESET = "\x1b[0m"
_ANSI_CYAN = "\x1b[36m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_MAGENTA = "\x1b[35m"
_ANSI_DEFAULT = "\x1b[0m"

def _resolved_width(*, width: int | None = None) -> int:
    if width is not None:
        return max(20, width)
    env_width = os.getenv("TOOL_CONTEXT_RELAY_WIDTH", "").strip()
    if env_width:
        try:
            return max(20, int(env_width))
        except ValueError:
            return 120
    return 120


def _color_enabled(*, stream) -> bool:
    if os.getenv("NO_COLOR") is not None:
        return False
    if os.getenv("TOOL_CONTEXT_RELAY_NO_COLOR") is not None:
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _wrap_prefixed(*, prefix: str, text: str, width: int) -> str:
    if not text:
        return prefix

    initial_indent = f"{prefix} "
    subsequent_indent = " " * len(initial_indent)

    wrapped_lines: list[str] = []
    for line in text.splitlines() or [""]:
        if not line.strip():
            wrapped_lines.append(prefix)
            continue
        wrapped_lines.append(
            textwrap.fill(
                line,
                width=width,
                initial_indent=initial_indent,
                subsequent_indent=subsequent_indent,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return "\n".join(wrapped_lines)


def _emit(*, prefix: str, color: str, text: str, stream, width: int | None = None) -> None:
    resolved_width = _resolved_width(width=width)
    message = _wrap_prefixed(prefix=prefix, text=text, width=resolved_width)
    if _color_enabled(stream=stream):
        stream.write(f"{color}{message}{_ANSI_RESET}\n")
    else:
        stream.write(f"{message}\n")
    stream.flush()


def emit_user(text: str, *, stream=None, width: int | None = None) -> None:
    _emit(prefix="USER:", color=_ANSI_CYAN, text=text, stream=stream or sys.stdout, width=width)


def emit_assistant(text: str, *, stream=None, width: int | None = None) -> None:
    _emit(
        prefix="ASSISTANT:",
        color=_ANSI_GREEN,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )


def emit_tool_request(text: str, *, stream=None, width: int | None = None) -> None:
    _emit(
        prefix="TOOL →",
        color=_ANSI_YELLOW,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )


def emit_tool_response(text: str, *, stream=None, width: int | None = None) -> None:
    _emit(
        prefix="TOOL ←",
        color=_ANSI_MAGENTA,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )

def emit_default(text: str, *, stream=None, width: int | None = None) -> None:
    _emit(
        prefix="## ",
        color=_ANSI_DEFAULT,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )