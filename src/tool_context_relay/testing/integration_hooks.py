from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agents import RunContextWrapper, Tool
from agents.lifecycle import RunHooksBase, TAgent


@dataclass
class CapturedToolCall:
    name: str
    arguments: dict[str, Any]
    result: str | None = None


class CaptureToolCalls(RunHooksBase[object, TAgent]):
    def __init__(self) -> None:
        super().__init__()
        self.tool_calls: list[CapturedToolCall] = []

    async def on_tool_start(
        self,
        context: RunContextWrapper[object],
        agent: TAgent,
        tool: Tool,
    ) -> None:
        raw_args = getattr(context, "tool_arguments", None)
        arguments: dict[str, Any] = {}
        if isinstance(raw_args, str) and raw_args.strip():
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                arguments = parsed

        tool_name = getattr(tool, "name", str(tool))
        self.tool_calls.append(CapturedToolCall(name=tool_name, arguments=arguments))

    async def on_tool_end(
        self,
        context: RunContextWrapper[object],
        agent: TAgent,
        tool: Tool,
        result: str,
    ) -> None:
        tool_name = getattr(tool, "name", str(tool))
        for call in reversed(self.tool_calls):
            if call.name == tool_name and call.result is None:
                call.result = result
                return

        self.tool_calls.append(CapturedToolCall(name=tool_name, arguments={}, result=result))


def require_tool_call_result(calls: list[CapturedToolCall], tool_name: str) -> str:
    for call in calls:
        if call.name == tool_name and isinstance(call.result, str):
            return call.result
    raise AssertionError(f"expected tool {tool_name!r} to be called with a result")


def assert_tool_called(calls: list[CapturedToolCall], tool_name: str) -> None:
    if any(call.name == tool_name for call in calls):
        return
    raise AssertionError(f"expected tool {tool_name!r} to be called")


def assert_tool_not_called(calls: list[CapturedToolCall], tool_name: str) -> None:
    if any(call.name == tool_name for call in calls):
        raise AssertionError(f"expected tool {tool_name!r} to NOT be called")


def assert_opaque_pass_through(
    *,
    calls: list[CapturedToolCall],
    opaque_reference: str,
    tool_name: str,
    argument_name: str,
    argument_filter: dict[str, str] | None = None,
) -> None:
    for call in calls:
        if call.name != tool_name:
            continue
        if argument_filter:
            if any(call.arguments.get(key) != value for key, value in argument_filter.items()):
                continue
        if call.arguments.get(argument_name) == opaque_reference:
            return

    filter_s = f", filter={argument_filter!r}" if argument_filter else ""
    raise AssertionError(
        f"expected {tool_name} to be called with {argument_name}={opaque_reference!r}{filter_s}"
    )

