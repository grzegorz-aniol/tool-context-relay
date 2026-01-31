import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent import build_agent
from tool_context_relay.agent.tool_definitions import collect_tool_definitions, print_tool_definitions


class ToolDefinitionsTests(unittest.TestCase):
    def test_collect_tool_definitions_has_expected_shape(self):
        agent = build_agent(model="test")
        definitions = collect_tool_definitions(agent.tools)

        self.assertTrue(definitions)
        self.assertTrue(all(isinstance(item.get("name"), str) for item in definitions))
        self.assertTrue(all(isinstance(item.get("description"), str) for item in definitions))
        self.assertTrue(all("params_json_schema" in item for item in definitions))

    def test_print_tool_definitions_emits_json(self):
        agent = build_agent(model="test")
        buf = io.StringIO()
        print_tool_definitions(agent.tools, stream=buf)
        output = buf.getvalue()

        self.assertTrue(output.startswith("tool-context-relay tools:\n"))
        self.assertIn('"name": "yt_transcribe"', output)

