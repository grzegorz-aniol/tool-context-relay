from __future__ import annotations

import json
from typing import Literal


BoxingMode = Literal["opaque", "json"]

RESOURCE_LINK_TYPE = "resource_link"
RESOURCE_LINK_KEYS = frozenset({"type", "uri"})


def _parse_resource_link_json(value: str) -> str | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if set(payload.keys()) != RESOURCE_LINK_KEYS:
        return None
    if payload.get("type") != RESOURCE_LINK_TYPE:
        return None
    uri = payload.get("uri")
    if not isinstance(uri, str):
        return None
    if not uri.startswith("internal://"):
        return None
    return uri


def extract_resource_uri(value: str) -> str | None:
    if value.startswith("internal://"):
        return value
    return _parse_resource_link_json(value)


def format_resource_link(uri: str) -> str:
    payload = {"type": RESOURCE_LINK_TYPE, "uri": uri}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "BoxingMode",
    "RESOURCE_LINK_TYPE",
    "RESOURCE_LINK_KEYS",
    "extract_resource_uri",
    "format_resource_link",
]
