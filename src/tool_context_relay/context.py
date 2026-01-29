from dataclasses import dataclass, field


@dataclass
class RelayContext:
    kv: dict[str, str] = field(default_factory=dict)
