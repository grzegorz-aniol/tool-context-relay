from dataclasses import dataclass, field

from tool_context_relay.boxing import BoxingMode


@dataclass
class RelayContext:
    kv: dict[str, str] = field(default_factory=dict)
    boxing_mode: BoxingMode = "opaque"
