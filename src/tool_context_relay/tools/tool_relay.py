from __future__ import annotations

from collections.abc import Callable, Sequence

from tool_context_relay.boxing import BoxingMode, extract_resource_uri, format_resource_link

cache: dict[str, str] = {}
MAX_RESULT_SIZE = 256


def _to_unsigned_64(value: int) -> int:
    return value & ((1 << 64) - 1)


def is_resource_id(value: str) -> bool:
    if len(value) >= 512:
        return False
    return extract_resource_uri(value) is not None


def unbox_value(value: str) -> str:
    resource_uri = extract_resource_uri(value)
    if resource_uri is None:
        return value
    return cache.get(resource_uri, "Unknown resource ID")


def box_value(value: str, *, mode: BoxingMode = "opaque") -> str:
    if len(value) > MAX_RESULT_SIZE:
        resource_hash = _to_unsigned_64(hash(value))
        resource_id = f"internal://{resource_hash:016x}"
        # We store value in in-memory cache, but the client may have different implementation (e.g. file based store)
        cache[resource_id] = value
        if mode == "json":
            return format_resource_link(resource_id)
        return resource_id
    return value


# ==> This is the core of the Tool Context Relay <==
# We are unboxing input arguments (resolving potential resource IDs to full text)
# and boxing output values (storing large outputs and returning resource IDs instead)
def tool_relay(func: Callable[..., str], args: Sequence[str], *, mode: BoxingMode = "opaque") -> str:
    relayed_args = [unbox_value(arg) for arg in args]
    value = func(*relayed_args)
    return box_value(value, mode=mode)
