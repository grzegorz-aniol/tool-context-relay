import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent.handler import _truncate, _format_tool_arguments, _tool_args_for_log


class ToolArgLoggingTests(unittest.TestCase):
    def test_truncate_limits_to_max_chars(self):
        self.assertEqual(_truncate("abc", max_chars=30), "abc")
        self.assertEqual(_truncate("a" * 30, max_chars=30), "a" * 30)
        self.assertEqual(_truncate("a" * 31, max_chars=30), ("a" * 27) + "...")

    def test_formats_json_object_as_key_value_pairs(self):
        args = '{"video_id": "123", "lang": "en"}'
        self.assertEqual(_format_tool_arguments(args), "video_id=123, lang=en")

    def test_truncates_keys_and_values_to_30_chars_each(self):
        long_key = "k" * 40
        long_value = "v" * 40
        args = f'{{\"{long_key}\": \"{long_value}\"}}'
        rendered = _format_tool_arguments(args)
        self.assertIn(("k" * 27) + "...", rendered)
        self.assertIn(("v" * 27) + "...", rendered)

    def test_non_json_arguments_fall_back_to_raw_truncated_string(self):
        raw = "x" * 40
        self.assertEqual(_format_tool_arguments(raw), ("x" * 27) + "...")

    def test_tool_args_for_log_reads_tool_arguments_attribute(self):
        ctx = SimpleNamespace(tool_arguments='{"a": "1"}')
        self.assertEqual(_tool_args_for_log(ctx), "a=1")

