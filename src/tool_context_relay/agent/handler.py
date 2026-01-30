from __future__ import annotations

import json
from typing import Sequence, Optional

from agents import RunContextWrapper, TContext, Tool, Agent, TResponseInputItem, ModelResponse
from agents.lifecycle import RunHooksBase, TAgent

from tool_context_relay.agent.pretty import (
    emit_tool_request,
    emit_tool_response,
    emit_user,
    emit_system,
    emit_assistant,
)


def _truncate(value: str, *, max_chars: int = 30) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


def _stringify_tool_arg_value(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _format_tool_arguments(tool_arguments: str) -> str:
    raw = tool_arguments.strip()
    if not raw:
        return ""

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _truncate(raw)

    if isinstance(parsed, dict):
        parts: list[str] = []
        for key, value in parsed.items():
            key_s = _truncate(str(key))
            value_s = _truncate(_stringify_tool_arg_value(value))
            parts.append(f"{key_s}={value_s}")
        return ", ".join(parts)

    return _truncate(_stringify_tool_arg_value(parsed))


def _tool_args_for_log(context: RunContextWrapper[object]) -> str:
    # The SDK passes a ToolContext (a RunContextWrapper subclass) into tool hooks.
    tool_arguments = getattr(context, "tool_arguments", None)
    if not isinstance(tool_arguments, str):
        return ""
    return _format_tool_arguments(tool_arguments)


def _get_field(obj: object, key: str) -> object | None:
    if isinstance(obj, dict):
        # This helper supports both the strongly-typed SDK models and plain dicts
        # (e.g. when inspecting cached/serialized outputs).
        return obj.get(key)
    return getattr(obj, key, None)


def _assistant_text_from_output_items(output: Sequence[object]) -> str:
    chunks: list[str] = []

    for item in output:
        if _get_field(item, "type") != "message":
            continue
        if _get_field(item, "role") != "assistant":
            continue

        content = _get_field(item, "content")
        if not isinstance(content, Sequence):
            continue

        for part in content:
            part_type = _get_field(part, "type")
            if part_type == "output_text":
                text = _get_field(part, "text")
                if isinstance(text, str) and text:
                    chunks.append(text)
            elif part_type == "refusal":
                refusal = _get_field(part, "refusal")
                if isinstance(refusal, str) and refusal:
                    chunks.append(refusal)

    return "".join(chunks).strip()


def _text_from_message_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, Sequence):
        return ""

    chunks: list[str] = []
    for part in content:
        part_type = _get_field(part, "type")
        if part_type in {"input_text", "output_text"}:
            text = _get_field(part, "text")
            if isinstance(text, str) and text:
                chunks.append(text)
        elif part_type == "text":
            text = _get_field(part, "text")
            if isinstance(text, str) and text:
                chunks.append(text)

    return "".join(chunks).strip()


def _user_texts_from_input_items(input_items: Sequence[object]) -> list[str]:
    texts: list[str] = []
    for item in input_items:
        if _get_field(item, "role") != "user":
            continue

        content = _get_field(item, "content")
        text = _text_from_message_content(content)
        if text:
            texts.append(text)
    return texts


class RunHookHandler(RunHooksBase[TContext, TAgent]):
    def __init__(self) -> None:
        super().__init__()
        self._seen_user_texts: set[str] = set()
        self._seen_system_prompts: set[str] = set()

    async def on_tool_start(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        tool: Tool,
    ) -> None:
        tool_name = getattr(tool, "name", str(tool))
        args_str = _tool_args_for_log(context)
        if args_str:
            emit_tool_request(f"{tool_name}({args_str})")
        else:
            emit_tool_request(tool_name)

    async def on_tool_end(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        tool: Tool,
        result: str,
    ) -> None:
        tool_name = getattr(tool, "name", str(tool))
        emit_tool_response(f"{tool_name} -> {result}")

    async def on_llm_start(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        system_prompt: Optional[str],
        input_items: list[TResponseInputItem],
    ) -> None:
        if system_prompt:
            prompt = system_prompt.strip()
            if prompt and prompt not in self._seen_system_prompts:
                self._seen_system_prompts.add(prompt)
                emit_system(prompt)

        for text in _user_texts_from_input_items(input_items):
            if text in self._seen_user_texts:
                continue
            self._seen_user_texts.add(text)
            emit_user(text)

    async def on_llm_end(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        response: ModelResponse,
    ) -> None:
        assistant_text = _assistant_text_from_output_items(response.output)
        if assistant_text:
            emit_assistant(assistant_text)
