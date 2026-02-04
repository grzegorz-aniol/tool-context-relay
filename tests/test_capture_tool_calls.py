from __future__ import annotations

import asyncio
from types import SimpleNamespace


def test_capture_tool_calls_delegates_and_captures() -> None:
    from tool_context_relay.testing.integration_hooks import CaptureToolCalls

    class Delegate:
        def __init__(self) -> None:
            self.started = 0
            self.ended = 0

        async def on_tool_start(self, context, agent, tool) -> None:  # noqa: ANN001
            self.started += 1

        async def on_tool_end(self, context, agent, tool, result) -> None:  # noqa: ANN001
            self.ended += 1

    delegate = Delegate()
    hooks = CaptureToolCalls(delegate=delegate)

    tool = SimpleNamespace(name="example_tool")
    context = SimpleNamespace(tool_arguments='{"x": 1}')

    asyncio.run(hooks.on_tool_start(context, None, tool))
    asyncio.run(hooks.on_tool_end(context, None, tool, "ok"))

    assert delegate.started == 1
    assert delegate.ended == 1
    assert [(c.name, c.arguments, c.result) for c in hooks.tool_calls] == [
        ("example_tool", {"x": 1}, "ok")
    ]

