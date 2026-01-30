from __future__ import annotations

import os
import sys
import textwrap
import weakref

_ANSI_RESET = "\x1b[0m"
_ANSI_CYAN = "\x1b[36m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_MAGENTA = "\x1b[35m"
_ANSI_DEFAULT = "\x1b[0m"

_default_group_by_stream: weakref.WeakKeyDictionary[object, str | None] = weakref.WeakKeyDictionary()
_default_active_by_stream: weakref.WeakKeyDictionary[object, bool] = weakref.WeakKeyDictionary()

def _mark_default_inactive(stream: object) -> None:
    try:
        _default_active_by_stream[stream] = False
    except TypeError:
        return


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


def _is_env_var_truthy(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return False
    return True


def _color_mode() -> str:
    mode = os.getenv("TOOL_CONTEXT_RELAY_COLOR")
    if mode is not None:
        normalized = mode.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return "always"
        if normalized in {"0", "false", "no", "off"}:
            return "never"
        if normalized in {"always", "auto", "never"}:
            return normalized
    if os.getenv("NO_COLOR") is not None:
        return "never"
    if os.getenv("TOOL_CONTEXT_RELAY_NO_COLOR") is not None:
        return "never"
    if _is_env_var_truthy("FORCE_COLOR"):
        return "always"
    return "auto"


def _color_enabled(*, stream) -> bool:
    mode = _color_mode()
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.getenv("TERM", "").strip().lower() == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())

def _wrap_body(*, text: str, width: int) -> str:
    if not text:
        return ""

    wrapped_lines: list[str] = []
    for line in text.splitlines() or [""]:
        if not line.strip():
            wrapped_lines.append("")
            continue
        wrapped_lines.append(
            textwrap.fill(
                line,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return "\n".join(wrapped_lines)

def _emit_colored_or_plain(*, stream, color: str, text: str) -> None:
    if _color_enabled(stream=stream):
        stream.write(f"{color}{text}{_ANSI_RESET}\n")
    else:
        stream.write(f"{text}\n")

def _emit(*, prefix: str, color: str, text: str, stream, width: int | None = None) -> None:
    resolved_width = _resolved_width(width=width)
    body = _wrap_body(text=text, width=resolved_width)
    # Always separate chat parts with an unstyled blank line.
    stream.write("\n")
    _emit_colored_or_plain(stream=stream, color=color, text=prefix)
    if body:
        stream.write("\n")
        _emit_colored_or_plain(stream=stream, color=color, text=body)
    stream.flush()


def emit_user(text: str, *, stream=None, width: int | None = None) -> None:
    _mark_default_inactive(stream or sys.stdout)
    _emit(prefix="USER:", color=_ANSI_CYAN, text=text, stream=stream or sys.stdout, width=width)


def emit_system(text: str, *, stream=None, width: int | None = None) -> None:
    _mark_default_inactive(stream or sys.stdout)
    _emit(prefix="SYSTEM:", color=_ANSI_CYAN, text=text, stream=stream or sys.stdout, width=width)


def emit_assistant(text: str, *, stream=None, width: int | None = None) -> None:
    _mark_default_inactive(stream or sys.stdout)
    _emit(
        prefix="ASSISTANT:",
        color=_ANSI_GREEN,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )


def emit_tool_request(text: str, *, stream=None, width: int | None = None) -> None:
    _mark_default_inactive(stream or sys.stdout)
    _emit(
        prefix="TOOL_CALL:",
        color=_ANSI_YELLOW,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )


def emit_tool_response(text: str, *, stream=None, width: int | None = None) -> None:
    _mark_default_inactive(stream or sys.stdout)
    _emit(
        prefix="TOOL_RESULT:",
        color=_ANSI_MAGENTA,
        text=text,
        stream=stream or sys.stdout,
        width=width,
    )


def emit_default(text: str, *, group: str | None = None, stream=None, width: int | None = None) -> None:
    resolved_stream = stream or sys.stdout
    resolved_width = _resolved_width(width=width)
    body = _wrap_body(text=text, width=resolved_width)
    if not body:
        return

    previous_group = _default_group_by_stream.get(resolved_stream)
    previous_active = _default_active_by_stream.get(resolved_stream, False)
    continuing = bool(group) and previous_active and previous_group == group

    if not continuing:
        resolved_stream.write("\n")
        headline = f"{group}:" if group else "##"
        _emit_colored_or_plain(stream=resolved_stream, color=_ANSI_DEFAULT, text=headline)
        try:
            _default_group_by_stream[resolved_stream] = group
            _default_active_by_stream[resolved_stream] = True
        except TypeError:
            pass

    _emit_colored_or_plain(stream=resolved_stream, color=_ANSI_DEFAULT, text=body)
    resolved_stream.flush()
