from __future__ import annotations

import json
from typing import Any, TextIO


def collect_tool_definitions(tools: list[Any]) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for tool in tools:
        definition: dict[str, Any] = {"name": getattr(tool, "name", None)}

        description = getattr(tool, "description", None)
        if description is not None:
            definition["description"] = description

        params_json_schema = getattr(tool, "params_json_schema", None)
        if params_json_schema is not None:
            definition["params_json_schema"] = params_json_schema

        definitions.append(definition)
    return definitions


def print_tool_definitions(tools: list[Any], *, stream: TextIO) -> None:
    stream.write("tool-context-relay tools:\n")
    stream.write(json.dumps(collect_tool_definitions(tools), ensure_ascii=False, indent=2))
    stream.write("\n")

