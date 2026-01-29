from __future__ import annotations

from inspect import getdoc

from agents import Agent, RunContextWrapper, function_tool

from tool_context_relay.context import RelayContext
from tool_context_relay.tool_relay import tool_relay, unwrap_body
from tool_context_relay.mcp_yt import fun_get_transcript
from tool_context_relay.mcp_deepcheck import fun_deep_check


def build_agent(*, model: str):
    def yt_transcribe(ctx: RunContextWrapper[RelayContext], video_id: str) -> str:
        return tool_relay(fun_get_transcript, [video_id])

    def deep_check(ctx: RunContextWrapper[RelayContext], text: str) -> str:
        return tool_relay(fun_deep_check, [text])

    def uncover_resource(ctx: RunContextWrapper[RelayContext], key: str) -> str:
        """Return the full text for an internal resource id (or echo the input)."""
        return unwrap_body(key)

    yt_transcribe.__doc__ = getdoc(fun_get_transcript)
    deep_check.__doc__ = getdoc(fun_deep_check)

    yt_transcribe = function_tool(yt_transcribe)
    deep_check = function_tool(deep_check)
    uncover_resource = function_tool(uncover_resource)

    return Agent(
        name="Tool Context Relay",
        instructions=(
            """
            Generate transcript of YT video with video_id='123' and then pass it for deep analysis.
            Use always tool when you need. 
            Keep responses concise.
            """
        ),
        model=model,
        tools=[uncover_resource, yt_transcribe, deep_check],
    )
