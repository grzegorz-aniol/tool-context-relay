from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoxingModeSpec:
    instructions: str
    examples: str
    internal_tool_docs: dict[str, str]
