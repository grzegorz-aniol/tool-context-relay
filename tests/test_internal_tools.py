import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent.agent import internal_resource_grep, internal_resource_read_lines
from tool_context_relay.tools.tool_relay import box_value


class InternalToolsTests(unittest.TestCase):
    def test_internal_resource_grep_returns_context(self):
        lines = [f"line {idx}" for idx in range(1, 25)]
        lines[8] = "before"
        lines[9] = "needle target"
        lines[10] = "after"
        text = "\n".join(lines) + "\n" + ("x" * 300)

        resource_id = box_value(text)
        result = internal_resource_grep(None, resource_id, "needle", 1)

        self.assertIn("Lines 9-11:", result)
        self.assertIn("9: before", result)
        self.assertIn("10: needle target", result)
        self.assertIn("11: after", result)

    def test_internal_resource_grep_returns_no_matches(self):
        text = "\n".join([f"line {idx}" for idx in range(1, 20)]) + ("x" * 300)
        resource_id = box_value(text)
        result = internal_resource_grep(None, resource_id, "missing", 0)
        self.assertEqual(result, "No matches found.")

    def test_internal_resource_read_lines_returns_expected_lines(self):
        lines = [f"line {idx}" for idx in range(1, 51)]
        text = "\n".join(lines)
        resource_id = box_value(text)

        result = internal_resource_read_lines(None, resource_id, 1, 2)
        self.assertEqual(result, "line 2\nline 3")

        tail = internal_resource_read_lines(None, resource_id, -2, 2)
        self.assertEqual(tail, "line 49\nline 50")
