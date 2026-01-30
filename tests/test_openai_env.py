import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.openai_env import (
    OPENAI_COMPAT_PROVIDER_KEY_ENV,
    resolve_provider,
    apply_api_key_override,
)


class OpenAIEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._prior: dict[str, str | None] = {}
        for key in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            OPENAI_COMPAT_PROVIDER_KEY_ENV,
        ):
            self._prior[key] = os.environ.get(key)

        for key in self._prior:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()

    def test_does_not_map_compat_key_when_no_base_url(self):
        os.environ[OPENAI_COMPAT_PROVIDER_KEY_ENV] = "sk-compat"
        apply_api_key_override(provider="auto")
        self.assertIsNone(os.environ.get("OPENAI_API_KEY"))

    def test_maps_compat_key_when_base_url_set(self):
        os.environ["OPENAI_BASE_URL"] = "http://example.test/v1"
        os.environ[OPENAI_COMPAT_PROVIDER_KEY_ENV] = "sk-compat"
        apply_api_key_override(provider="auto")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-compat")

    def test_does_not_override_openai_api_key_without_tool_var(self):
        os.environ["OPENAI_API_KEY"] = "sk-existing"
        apply_api_key_override(provider="auto")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-existing")

    def test_ignores_whitespace_tool_var(self):
        os.environ["OPENAI_BASE_URL"] = "http://example.test/v1"
        os.environ[OPENAI_COMPAT_PROVIDER_KEY_ENV] = "   "
        apply_api_key_override(provider="auto")
        self.assertIsNone(os.environ.get("OPENAI_API_KEY"))

    def test_explicit_provider_openai_does_not_map(self):
        os.environ["OPENAI_BASE_URL"] = "http://example.test/v1"
        os.environ[OPENAI_COMPAT_PROVIDER_KEY_ENV] = "sk-compat"
        apply_api_key_override(provider="openai")
        self.assertIsNone(os.environ.get("OPENAI_API_KEY"))

    def test_explicit_provider_openai_compat_maps_without_base_url(self):
        os.environ[OPENAI_COMPAT_PROVIDER_KEY_ENV] = "sk-compat"
        apply_api_key_override(provider="openai-compat")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-compat")

    def test_resolve_provider_auto(self):
        self.assertEqual(resolve_provider("auto"), "openai")
        os.environ["OPENAI_BASE_URL"] = "http://example.test/v1"
        self.assertEqual(resolve_provider("auto"), "openai-compat")
