import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.tool_relay import tool_relay, unwrap_body


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
        self.assertEqual(unwrap_body(resource_id), "x" * 2048)
