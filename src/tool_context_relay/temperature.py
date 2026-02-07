from __future__ import annotations

import math


def ensure_valid_temperature(value: float, *, label: str | None = None) -> float:
    """Validate a temperature value is finite and in [0.0, 2.0]."""
    label_text = label or "Temperature"
    if not math.isfinite(value):
        raise ValueError(f"{label_text} must be a finite number.")
    if value < 0.0 or value > 2.0:
        raise ValueError(f"{label_text} must be between 0.0 and 2.0.")
    return value


def parse_temperature_from_env(value: str, *, label: str) -> float:
    """Parse and validate a temperature pulled from an environment variable."""
    try:
        parsed = float(value)
    except ValueError:
        raise ValueError(f"{label} must be a number.")
    return ensure_valid_temperature(parsed, label=label)
