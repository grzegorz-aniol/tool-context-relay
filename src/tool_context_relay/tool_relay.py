from __future__ import annotations

from collections.abc import Callable, Sequence

cache: dict[str, str] = {}
MAX_RESULT_SIZE = 256

def is_resource_id(body: str) -> bool:
    return len(body) < 128 and body.startswith("internal://")


def unwrap_body(body: str) -> str:
    if is_resource_id(body):
        return cache.get(body, "Unknown resource ID")
    return body


def tool_relay(func: Callable[..., str], args: Sequence[str]) -> str:
    relayed_args = [unwrap_body(arg) for arg in args]
    value = func(*relayed_args)
    if len(value) > 1024:
        resource_id = f"internal://{hash(value)}"
        cache[resource_id] = value
        return resource_id
    return value
