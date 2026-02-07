import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.openai_env import ProfileConfig, apply_profile, load_profile


class OpenAIEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        keys = (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_MODEL",
            "OPENAI_COMPAT_API_KEY",
            "OPENAI_PROVIDER",
            "BIELIK_API_KEY",
            "BIELIK_BASE_URL",
            "BIELIK_PROVIDER",
            "BIELIK_MODEL",
            "BIELIK_BACKEND_PROVIDER",
        )
        self._prior: dict[str, str | None] = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()

    def test_load_profile_defaults_to_openai(self):
        os.environ["OPENAI_API_KEY"] = "sk-openai"
        config = load_profile("OpenAI")
        self.assertEqual(config.provider, "openai")
        self.assertIsNone(config.endpoint)
        self.assertEqual(config.api_key, "sk-openai")

    def test_load_profile_uses_openai_default_even_with_endpoint(self):
        os.environ["BIELIK_BASE_URL"] = "http://localhost:1234/v1"
        os.environ["BIELIK_API_KEY"] = "sk-bielik"
        config = load_profile("   bielik   ")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.endpoint, "http://localhost:1234/v1")
        self.assertEqual(config.api_key, "sk-bielik")

    def test_load_profile_requires_endpoint_for_non_openai(self):
        os.environ["BIELIK_PROVIDER"] = "openai-compat"
        with self.assertRaises(RuntimeError):
            load_profile("bielik")

    def test_load_profile_obeys_provider_env(self):
        os.environ["BIELIK_PROVIDER"] = "openrouter"
        os.environ["BIELIK_BASE_URL"] = "http://localhost:1234/v1"
        os.environ["BIELIK_API_KEY"] = "sk-bielik"
        config = load_profile("bielik")
        self.assertEqual(config.provider, "openrouter")
        self.assertIsNone(config.backend_provider)

    def test_load_profile_reads_model_provider(self):
        os.environ["BIELIK_PROVIDER"] = "openrouter"
        os.environ["BIELIK_BASE_URL"] = "http://localhost:1234/v1"
        os.environ["BIELIK_API_KEY"] = "sk-bielik"
        os.environ["BIELIK_BACKEND_PROVIDER"] = "anthropic"
        config = load_profile("bielik")
        self.assertEqual(config.backend_provider, "anthropic")

    def test_load_profile_reads_compat_api_key_alias(self):
        os.environ["OPENAI_BASE_URL"] = "http://localhost:1234/v1"
        os.environ["OPENAI_COMPAT_API_KEY"] = "sk-compat"
        config = load_profile("openai")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.api_key, "sk-compat")

    def test_apply_profile_sets_env_vars(self):
        config = ProfileConfig(
            name="test",
            prefix="TEST",
            provider="openai-compat",
            endpoint="http://endpoint/v1",
            api_key="sk-test",
            default_model="gpt-test",
            backend_provider="openrouter",
        )
        apply_profile(config)
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-test")
        self.assertEqual(os.environ.get("OPENAI_BASE_URL"), "http://endpoint/v1")
        self.assertEqual(os.environ.get("OPENAI_API_BASE"), "http://endpoint/v1")
