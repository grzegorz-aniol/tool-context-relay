import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_agent_instructions_are_generic_and_mention_opaque_references() -> None:
    from tool_context_relay.agent.agent import build_agent

    agent = build_agent(model="dummy")
    instructions = str(agent.instructions)

    assert "YouTube" not in instructions
    assert "transcript" not in instructions.lower()
    assert "google drive" not in instructions.lower()

    assert "you may answer directly" in instructions.lower()
    assert "tools only when needed" in instructions.lower()

    assert "opaque reference" in instructions.lower()
    assert "optional" in instructions.lower()
    assert "internal://" in instructions
    assert "preferred way to move large text" in instructions.lower()
    assert "any tool argument that expects text" in instructions.lower()
    assert "always try passing the opaque reference" in instructions.lower()
    assert "do not resolve an opaque reference just to re-send it to another tool" in instructions.lower()
    assert "general (always):" not in instructions.lower()
    assert "opaque references (only if they appear):" not in instructions.lower()


@pytest.mark.parametrize(
    ("fewshots", "expected_present"),
    [
        (False, False),
        (True, True),
    ],
)
def test_agent_instructions_include_fewshots_only_when_enabled(
    *, fewshots: bool, expected_present: bool
) -> None:
    from tool_context_relay.agent.agent import build_agent

    agent = build_agent(model="dummy", fewshots=fewshots)
    instructions = str(agent.instructions)
    marker = "Examples (follow exactly):"

    assert (marker in instructions) is expected_present


def test_agent_instructions_enable_fewshots_by_default() -> None:
    from tool_context_relay.agent.agent import build_agent

    agent = build_agent(model="dummy")
    instructions = str(agent.instructions)

    assert "Examples (follow exactly):" in instructions


def test_agent_exposes_only_new_internal_resource_tools() -> None:
    from tool_context_relay.agent.agent import build_agent

    agent = build_agent(model="dummy")
    tool_names = {tool.name for tool in agent.tools}

    assert "internal_resource_read" in tool_names
    assert "internal_resource_read_slice" in tool_names
    assert "internal_resource_length" in tool_names


def test_internal_resource_tools_resolve_boxed_values() -> None:
    from tool_context_relay.agent.agent import (
        internal_resource_length,
        internal_resource_read,
        internal_resource_read_slice,
    )
    from tool_context_relay.tools.tool_relay import box_value

    value = "x" * 2048
    resource_id = box_value(value)
    assert resource_id.startswith("internal://")

    assert internal_resource_length(None, resource_id) == str(len(value))
    assert internal_resource_read(None, resource_id) == value
    assert internal_resource_read_slice(None, resource_id, 10, 5) == value[10:15]


def test_internal_resource_tools_accept_json_boxing() -> None:
    from tool_context_relay.agent.agent import (
        internal_resource_length,
        internal_resource_read,
        internal_resource_read_slice,
    )
    from tool_context_relay.tools.tool_relay import box_value

    value = "x" * 2048
    boxed = box_value(value, mode="json")

    assert internal_resource_length(None, boxed) == str(len(value))
    assert internal_resource_read(None, boxed) == value
    assert internal_resource_read_slice(None, boxed, 10, 5) == value[10:15]
