from __future__ import annotations

from tool_context_relay.agent.boxing_modes.base import BoxingModeSpec
from tool_context_relay.agent.boxing_modes.json import SPEC as JSON_SPEC
from tool_context_relay.agent.boxing_modes.opaque import SPEC as OPAQUE_SPEC
from tool_context_relay.boxing import BoxingMode


def get_boxing_mode_spec(mode: BoxingMode) -> BoxingModeSpec:
    if mode == "json":
        return JSON_SPEC
    return OPAQUE_SPEC


__all__ = ["BoxingModeSpec", "get_boxing_mode_spec"]
