from __future__ import annotations

from inspect import getdoc
from textwrap import dedent

from agents import Agent, RunContextWrapper, function_tool
from agents.models.interface import Model

from tool_context_relay.agent.context import RelayContext
from tool_context_relay.tools.mcp_google_drive import fun_write_file_to_google_drive
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_yt import fun_get_transcript
from tool_context_relay.tools.tool_relay import tool_relay, unbox_value, is_resource_id


## ===================================================================================================
# We need wrap tool calls with a wrapper that will unbox/box arguments/results
# This could be done internally by a framework, but here we do it manually for demonstration purposes
# We simulate here some real MCP Server tools
## ===================================================================================================

def yt_transcribe(ctx: RunContextWrapper[RelayContext], video_id: str) -> str:
    return tool_relay(fun_get_transcript, [video_id])


def deep_check(ctx: RunContextWrapper[RelayContext], text: str) -> str:
    return tool_relay(fun_deep_check, [text])


def google_drive_write_file(
        ctx: RunContextWrapper[RelayContext], file_content: str, file_name: str
) -> str:
    return tool_relay(fun_write_file_to_google_drive, [file_content, file_name])

# Technical trick: we copy docstrings from original functions to the wrapped versions
# This will generate tool definitions with proper documentation
yt_transcribe.__doc__ = getdoc(fun_get_transcript)
deep_check.__doc__ = getdoc(fun_deep_check)
google_drive_write_file.__doc__ = getdoc(fun_write_file_to_google_drive)

## ===================================================================================================
## Internal functions to manipulate on boxed resource
## ===================================================================================================

def unbox_resource(ctx: RunContextWrapper[RelayContext], internal_resource_id: str) -> str:
    """Return the full text for an internal resource id (or echo the input).

    Args:
        internal_resource_id (str): The internal resource ID to unbox.
    Returns:
        str: The unboxed value.
    """
    if not is_resource_id(internal_resource_id):
        return f"Value {internal_resource_id!r} is not a valid internal resource ID"
    return unbox_value(internal_resource_id)


def unbox_partially_resource(ctx: RunContextWrapper[RelayContext], internal_resource_id: str, starting_index: int,
                             length: int) -> str:
    """Unbox just part of any internal resource."""
    if not is_resource_id(internal_resource_id):
        return f"Value {internal_resource_id!r} is not a valid internal resource ID"
    value = unbox_value(internal_resource_id)[starting_index:starting_index + length]
    return value


def get_unboxed_resource_length(ctx: RunContextWrapper[RelayContext], internal_resource_id: str) -> str:
    """Get length of unboxed resource."""
    if not is_resource_id(internal_resource_id):
        return f"Value {internal_resource_id!r} is not a valid internal resource ID"
    value = unbox_value(internal_resource_id)
    return str(len(value))


def build_agent(*, model: str | Model):

    # Prepare tool definitions based on python functions (we use explicitly function_tool decorator)
    tool_yt_transcribe = function_tool(yt_transcribe)
    tool_deep_check = function_tool(deep_check)
    tool_google_drive_write_file = function_tool(google_drive_write_file)
    tool_unbox_resource = function_tool(unbox_resource)
    tool_unbox_partially_resource = function_tool(unbox_partially_resource)
    tool_get_unboxed_resource_length = function_tool(get_unboxed_resource_length)

    instructions = dedent(
        """
        Generate transcript of YT video with video_id='123' and then pass it for deep analysis.

        Be concise.

        Use tools whenever needed to answer correctly.

        Tools may accept/return boxed long values as internal resource IDs: `internal://<hash>`.
        Treat these as opaque strings: pass through unchanged.
        Avoid unboxing unless necessary; if needed, call `unbox_resource`.
        Never create non existing resource IDs on your own. Use only those returned by tools.
        """
    ).strip()

    return Agent(
        name="Tool Context Relay",
        instructions=instructions,
        model=model,
        tools=[
            tool_yt_transcribe, tool_deep_check, tool_google_drive_write_file,
            tool_unbox_resource, tool_unbox_partially_resource, tool_get_unboxed_resource_length
        ],
    )
