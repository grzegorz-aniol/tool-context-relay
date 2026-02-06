from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch


def test_handler_counts_tool_calls_and_resource_ids() -> None:
    from tool_context_relay.agent.handler import RunHookHandler
    from tool_context_relay.tools.tool_relay import box_value

    handler = RunHookHandler()
    tool = SimpleNamespace(name="example_tool")
    context = SimpleNamespace(tool_arguments='{"text": "internal://deadbeef"}')

    with (
        patch("tool_context_relay.agent.handler.emit_tool_request") as emit_tool_request,
        patch("tool_context_relay.agent.handler.emit_tool_request_opaque") as emit_tool_request_opaque,
        patch("tool_context_relay.agent.handler.emit_tool_response") as emit_tool_response,
    ):
        asyncio.run(handler.on_tool_start(context, None, tool))
        asyncio.run(handler.on_tool_end(context, None, tool, "not-opaque"))
        asyncio.run(handler.on_tool_end(context, None, tool, box_value("x" * 2048)))

    assert handler.tool_calls == 1
    assert handler.tool_calls_with_resource_id_args == 1
    assert handler.tool_results_with_resource_id == 1
    emit_tool_request.assert_not_called()
    emit_tool_request_opaque.assert_called()
    emit_tool_response.assert_called()


def test_handler_detects_json_boxed_resource_ids() -> None:
    from tool_context_relay.agent.handler import RunHookHandler
    from tool_context_relay.tools.tool_relay import box_value

    handler = RunHookHandler()
    tool = SimpleNamespace(name="example_tool")
    json_ref = "{\"type\":\"resource_link\",\"uri\":\"internal://deadbeef\"}"
    context = SimpleNamespace(tool_arguments=f'{{"text": "{json_ref}"}}')

    with (
        patch("tool_context_relay.agent.handler.emit_tool_request") as emit_tool_request,
        patch("tool_context_relay.agent.handler.emit_tool_request_opaque") as emit_tool_request_opaque,
        patch("tool_context_relay.agent.handler.emit_tool_response") as emit_tool_response,
    ):
        asyncio.run(handler.on_tool_start(context, None, tool))
        asyncio.run(handler.on_tool_end(context, None, tool, box_value("x" * 2048, mode="json")))

    assert handler.tool_calls == 1
    assert handler.tool_calls_with_resource_id_args == 1
    assert handler.tool_results_with_resource_id == 1
    emit_tool_request.assert_not_called()
    emit_tool_request_opaque.assert_called()
    emit_tool_response.assert_called()
