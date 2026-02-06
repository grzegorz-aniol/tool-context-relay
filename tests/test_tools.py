import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.tools.tool_relay import tool_relay, unbox_value, box_value, is_resource_id
from tool_context_relay.tools.mcp_yt import fun_get_transcript


class ToolsTests(unittest.TestCase):
    def test_tool_relay_forwards_args_positionally(self):
        def echo(value: str) -> str:
            return value

        self.assertEqual(tool_relay(echo, ["hello"]), "hello")

    def test_tool_relay_wraps_large_outputs_as_resource_id(self):
        def big(value: str) -> str:
            return value * 2048

        resource_id = tool_relay(big, ["x"])
        self.assertTrue(resource_id.startswith("internal://"))
        self.assertEqual(unbox_value(resource_id), "x" * 2048)

    def test_tool_relay_resource_id_never_contains_negative_sign(self):
        def big(value: str) -> str:
            return value * 2048

        with patch("builtins.hash", return_value=-1):
            resource_id = tool_relay(big, ["x"])

        self.assertTrue(resource_id.startswith("internal://"))
        self.assertNotIn("-", resource_id)
        self.assertEqual(unbox_value(resource_id), "x" * 2048)

    def test_fun_get_transcript_returns_short_value_for_special_id(self):
        self.assertEqual(fun_get_transcript("999"), "Welcome in a new episode and good bye")

    def test_box_value_json_mode_returns_resource_link_string(self):
        value = "x" * 2048
        boxed = box_value(value, mode="json")
        self.assertIsInstance(boxed, str)
        self.assertIn('"type":"resource_link"', boxed)
        self.assertTrue(is_resource_id(boxed))
        self.assertEqual(unbox_value(boxed), value)
