import unittest

from agents import ModelSettings

from tool_context_relay.main import _build_model_settings


class BuildModelSettingsTests(unittest.TestCase):
    def test_returns_none_when_no_temperature_and_openai(self):
        settings = _build_model_settings(
            temperature=None,
            provider="openai",
            backend_provider=None,
        )
        self.assertIsNone(settings)

    def test_includes_temperature_only(self):
        settings = _build_model_settings(
            temperature=0.7,
            provider="openai",
            backend_provider=None,
        )
        self.assertIsInstance(settings, ModelSettings)
        self.assertEqual(settings.temperature, 0.7)
        self.assertIsNone(settings.extra_args)

    def test_openai_compat_does_not_set_provider_payload(self):
        settings = _build_model_settings(
            temperature=None,
            provider="openai-compat",
            backend_provider=None,
        )
        self.assertIsNone(settings)

    def test_openrouter_includes_data_collection_flag(self):
        settings = _build_model_settings(
            temperature=None,
            provider="openrouter",
            backend_provider="anthropic",
        )
        self.assertIsInstance(settings, ModelSettings)
        self.assertEqual(
            settings.extra_body,
            {"provider": {"allow_fallbacks": False, "data_collection": "deny", "order": ["anthropic"]}},
        )
