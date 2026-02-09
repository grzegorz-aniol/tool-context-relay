from __future__ import annotations

from inspect import getdoc
from textwrap import dedent

from agents import Agent, ModelSettings, RunContextWrapper, function_tool
from agents.models.interface import Model

from tool_context_relay.agent.context import RelayContext
from tool_context_relay.tools.mcp_google_drive import fun_write_file_to_google_drive
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_yt import fun_get_transcript
from tool_context_relay.boxing import BoxingMode
from tool_context_relay.agent.boxing_modes import get_boxing_mode_spec
from tool_context_relay.tools.tool_relay import tool_relay, unbox_value, is_resource_id


## ===================================================================================================
# We need wrap tool calls with a wrapper that will unbox/box arguments/results
# This could be done internally by a framework, but here we do it manually for demonstration purposes
# We simulate here some real MCP Server tools
## ===================================================================================================

def _get_boxing_mode(ctx: RunContextWrapper[RelayContext] | None) -> BoxingMode:
    if ctx is None:
        return "opaque"
    context = getattr(ctx, "context", None)
    mode = getattr(context, "boxing_mode", "opaque")
    if mode in {"opaque", "json"}:
        return mode
    return "opaque"


def yt_transcribe(ctx: RunContextWrapper[RelayContext], video_id: str) -> str:
    return tool_relay(fun_get_transcript, [video_id], mode=_get_boxing_mode(ctx))


def deep_check(ctx: RunContextWrapper[RelayContext], text: str) -> str:
    return tool_relay(fun_deep_check, [text], mode=_get_boxing_mode(ctx))


def google_drive_write_file(
        ctx: RunContextWrapper[RelayContext], file_content: str, file_name: str
) -> str:
    return tool_relay(fun_write_file_to_google_drive, [file_content, file_name], mode=_get_boxing_mode(ctx))

# Technical trick: we copy docstrings from original functions to the wrapped versions
# This will generate tool definitions with proper documentation
yt_transcribe.__doc__ = getdoc(fun_get_transcript)
deep_check.__doc__ = getdoc(fun_deep_check)
google_drive_write_file.__doc__ = getdoc(fun_write_file_to_google_drive)

## ===================================================================================================
## Internal tools to resolve opaque references
## ===================================================================================================

def internal_resource_read(ctx: RunContextWrapper[RelayContext], opaque_reference: str) -> str:
    """Resolve an opaque reference and return its full value (or echo the input).

    Args:
        opaque_reference (str): Opaque reference like `internal://<id>`.
    Returns:
        str: The resolved value.
    """
    if not is_resource_id(opaque_reference):
        return f"Value {opaque_reference!r} is not a valid opaque reference"
    return unbox_value(opaque_reference)


def internal_resource_read_slice(
    ctx: RunContextWrapper[RelayContext],
    opaque_reference: str,
    start_index: int,
    length: int,
) -> str:
    """Resolve and return just a slice of an opaque reference.

    Supports negative start indices (Python-style) to count from the end.
    """
    if not is_resource_id(opaque_reference):
        return f"Value {opaque_reference!r} is not a valid opaque reference"
    value = unbox_value(opaque_reference)
    start = start_index
    if start_index < 0:
        start = max(len(value) + start_index, 0)
    end = start + length
    return value[start:end]


def internal_resource_length(ctx: RunContextWrapper[RelayContext], opaque_reference: str) -> str:
    """Return the length of the value behind an opaque reference."""
    if not is_resource_id(opaque_reference):
        return f"Value {opaque_reference!r} is not a valid opaque reference"
    value = unbox_value(opaque_reference)
    return str(len(value))


def build_agent(
    *,
    model: str | Model,
    fewshots: bool = True,
    temperature: float | None = None,
    model_settings: ModelSettings | None = None,
    boxing_mode: BoxingMode = "opaque",
) -> Agent:

    # Prepare tool definitions based on python functions (we use explicitly function_tool decorator)
    tool_yt_transcribe = function_tool(yt_transcribe)
    tool_deep_check = function_tool(deep_check)
    tool_google_drive_write_file = function_tool(google_drive_write_file)
    spec = get_boxing_mode_spec(boxing_mode)
    internal_docs = spec.internal_tool_docs
    internal_resource_read.__doc__ = internal_docs.get(
        "internal_resource_read",
        internal_resource_read.__doc__,
    )
    internal_resource_read_slice.__doc__ = internal_docs.get(
        "internal_resource_read_slice",
        internal_resource_read_slice.__doc__,
    )
    internal_resource_length.__doc__ = internal_docs.get(
        "internal_resource_length",
        internal_resource_length.__doc__,
    )

    tool_internal_resource_read = function_tool(internal_resource_read)
    tool_internal_resource_read_slice = function_tool(internal_resource_read_slice)
    tool_internal_resource_length = function_tool(internal_resource_length)

    # Part 1/3: general agent behavior. Applies to all tasks, regardless of whether tools are used.
    general_instructions = dedent(
        """
        - Be concise.
        - You may answer directly without tools when possible.
        - Use tools only when needed to answer correctly or to perform an action.
        - Do not claim an action was completed unless you actually called a tool and received its result.
        - If the user already provided required inputs anywhere in the conversation (even embedded like key='value'),
          extract them and proceed; do not ask for them again.
        - For multi-step requests, call tools sequentially and pass outputs to the next tool.
        """
    ).strip()

    instruction_parts = [general_instructions, spec.instructions]
    if fewshots:
        instruction_parts.append(spec.examples)
    instructions = "\n\n".join(instruction_parts)

    agent_kwargs: dict[str, object] = {}

    merged_model_settings = model_settings
    if merged_model_settings is None and temperature is not None:
        merged_model_settings = ModelSettings(temperature=temperature)
    elif merged_model_settings is not None and temperature is not None:
        merged_model_settings = merged_model_settings.resolve(ModelSettings(temperature=temperature))

    if merged_model_settings is not None:
        agent_kwargs["model_settings"] = merged_model_settings

    return Agent(
        name="Tool Context Relay",
        instructions=instructions,
        model=model,
        tools=[
            tool_yt_transcribe, tool_deep_check, tool_google_drive_write_file,
            tool_internal_resource_read, tool_internal_resource_read_slice, tool_internal_resource_length
        ],
        **agent_kwargs,
    )
