from __future__ import annotations

from inspect import getdoc
from textwrap import dedent

from agents import Agent, RunContextWrapper, function_tool

from tool_context_relay.agent.context import RelayContext
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_yt import fun_get_transcript
from tool_context_relay.tools.tool_relay import tool_relay, unbox_value


def build_agent(*, model: str):

    # We need wrap tool calls with a wrapper that will unbox/box arguments/results
    # This could be done internally by a framework, but here we do it manually for demonstration purposes

    def yt_transcribe(ctx: RunContextWrapper[RelayContext], video_id: str) -> str:
        return tool_relay(fun_get_transcript, [video_id])

    def deep_check(ctx: RunContextWrapper[RelayContext], text: str) -> str:
        return tool_relay(fun_deep_check, [text])

    def unbox_resource(ctx: RunContextWrapper[RelayContext], key: str) -> str:
        """Return the full text for an internal resource id (or echo the input)."""
        return unbox_value(key)

    yt_transcribe.__doc__ = getdoc(fun_get_transcript)
    deep_check.__doc__ = getdoc(fun_deep_check)

    yt_transcribe = function_tool(yt_transcribe)
    deep_check = function_tool(deep_check)
    unbox_resource_tool = function_tool(unbox_resource)

    instructions = dedent(
        """
        Generate transcript of YT video with video_id='123' and then pass it for deep analysis.
        Use always tool when you need.
        Keep responses concise.

        You should be aware the tools may return and accept in argument an internal resource ID instead of a full text.
        Internal resource ID form is `internal://<hash>`.
        Just accept this and pass as a regular argument to the tool with no modification.
        """
    ).strip()

    return Agent(
        name="Tool Context Relay",
        instructions=instructions,
        model=model,
        tools=[unbox_resource_tool, yt_transcribe, deep_check],
    )
