from __future__ import annotations

from collections.abc import Callable, Sequence

cache: dict[str, str] = {}
MAX_RESULT_SIZE = 256


def _to_unsigned_64(value: int) -> int:
    return value & ((1 << 64) - 1)


def is_resource_id(value: str) -> bool:
    return len(value) < 128 and value.startswith("internal://")


def unbox_value(value: str) -> str:
    if is_resource_id(value):
        return cache.get(value, "Unknown resource ID")
    return value


def box_value(value: str) -> str:
    if len(value) > MAX_RESULT_SIZE:
        resource_hash = _to_unsigned_64(hash(value))
        resource_id = f"internal://{resource_hash:016x}"
        cache[resource_id] = value
        return resource_id
    return value


# ==> This is the core of the idea <==
# We are unboxing input arguments (resolving potential resource IDs to full text)
# and boxing output values (storing large outputs and returning resource IDs instead)
def tool_relay(func: Callable[..., str], args: Sequence[str]) -> str:
    relayed_args = [unbox_value(arg) for arg in args]
    value = func(*relayed_args)
    return box_value(value)
