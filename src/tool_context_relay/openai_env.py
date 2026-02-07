from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Sequence

from tool_context_relay.temperature import parse_temperature_from_env


_BASE_URL_KEYS = ("BASE_URL", "BASEURL", "API_BASE", "ENDPOINT")
_API_KEY_SUFFIXES = ("API_KEY", "COMPAT_API_KEY")


def _getenv_stripped(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _first_env_value(prefix: str, keys: Sequence[str]) -> str | None:
    for key in keys:
        value = _getenv_stripped(f"{prefix}_{key}")
        if value is not None:
            return value
    return None


def _normalize_profile_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("profile name must not be empty")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not normalized:
        raise ValueError("profile name must contain letters or digits")
    return normalized.upper()


def _normalize_provider_name(value: str | None) -> str:
    if value is None:
        return "openai"
    normalized = value.strip().lower()
    return normalized or "openai"


def _provider_requires_endpoint(provider: str) -> bool:
    return provider not in {"openai"}


def _load_profile_temperature(prefix: str) -> float | None:
    raw = _getenv_stripped(f"{prefix}_TEMPERATURE")
    if raw is None:
        return None
    return parse_temperature_from_env(raw, label=f"{prefix}_TEMPERATURE")


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    prefix: str
    provider: str
    endpoint: str | None
    api_key: str | None
    default_model: str | None
    backend_provider: str | None
    temperature: float | None


def load_profile(profile: str) -> ProfileConfig:
    """Load profile configuration values from environment variables."""
    normalized = _normalize_profile_name(profile)
    provider = _normalize_provider_name(_getenv_stripped(f"{normalized}_PROVIDER"))
    provider_prefix = provider.upper()

    profile_endpoint = _first_env_value(normalized, _BASE_URL_KEYS)
    provider_endpoint = _first_env_value(provider_prefix, _BASE_URL_KEYS)
    endpoint = profile_endpoint or provider_endpoint
    if _provider_requires_endpoint(provider) and endpoint is None:
        raise RuntimeError(
            f"profile '{profile}' selects provider '{provider}' but {provider_prefix}_BASE_URL / "
            f"{provider_prefix}_BASEURL / {provider_prefix}_API_BASE / {provider_prefix}_ENDPOINT "
            "is not configured"
        )

    profile_api_key = _first_env_value(normalized, _API_KEY_SUFFIXES)
    provider_api_key = _first_env_value(provider_prefix, _API_KEY_SUFFIXES)
    api_key = profile_api_key or provider_api_key
    if provider == "openai" and api_key is None and normalized == "OPENAI":
        api_key = _getenv_stripped("OPENAI_COMPAT_API_KEY")

    default_model = _getenv_stripped(f"{normalized}_MODEL")
    backend_provider = _getenv_stripped(f"{normalized}_BACKEND_PROVIDER")
    temperature = _load_profile_temperature(normalized)

    return ProfileConfig(
        name=profile,
        prefix=normalized,
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        default_model=default_model,
        backend_provider=backend_provider,
        temperature=temperature,
    )


def apply_profile(profile: ProfileConfig) -> None:
    """Apply profile-derived values to the legacy OpenAI env vars."""
    if profile.api_key is not None:
        os.environ["OPENAI_API_KEY"] = profile.api_key
    if profile.endpoint is not None:
        os.environ["OPENAI_BASE_URL"] = profile.endpoint
        os.environ["OPENAI_API_BASE"] = profile.endpoint
