import os
from typing import Literal


OPENAI_COMPAT_PROVIDER_KEY_ENV = "OPENAI_COMPAT_API_KEY"

Provider = Literal["auto", "openai", "openai-compat"]
ResolvedProvider = Literal["openai", "openai-compat"]


def _getenv_stripped(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def using_openai_compatible_endpoint() -> bool:
    """Return True when talking to a non-default OpenAI-compatible base URL.

    The OpenAI Python SDK and Agents SDK commonly use OPENAI_BASE_URL (and/or
    OPENAI_API_BASE) to override the default endpoint.
    """
    return _getenv_stripped("OPENAI_BASE_URL") is not None or _getenv_stripped("OPENAI_API_BASE") is not None


def resolve_provider(provider: Provider) -> ResolvedProvider:
    if provider == "auto":
        return "openai-compat" if using_openai_compatible_endpoint() else "openai"
    return provider


def apply_api_key_override(*, provider: Provider) -> None:
    """Map tool-specific provider env vars to OPENAI_API_KEY for the SDKs.

    Rules:
    - Provider 'openai': rely on OPENAI_API_KEY (do not remap).
    - Provider 'openai-compat': read OPENAI_COMPAT_API_KEY and map
      it to OPENAI_API_KEY for this process.
    """
    if resolve_provider(provider) != "openai-compat":
        return

    token = _getenv_stripped(OPENAI_COMPAT_PROVIDER_KEY_ENV)
    if token is None:
        return

    os.environ["OPENAI_API_KEY"] = token
