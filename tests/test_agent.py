import sys
import unittest
from inspect import getdoc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent import build_agent
from tool_context_relay.tools.google_drive import fun_write_file_to_google_drive
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_yt import fun_get_transcript


class AgentTests(unittest.TestCase):
    def test_agent_tools_expose_underlying_docstrings(self):
        agent = build_agent(model="test")
        tools_by_name = {tool.name: tool for tool in agent.tools}

        yt_tool = tools_by_name["yt_transcribe"]
        self.assertEqual(yt_tool.description, getdoc(fun_get_transcript).splitlines()[0])
        self.assertEqual(
            yt_tool.params_json_schema["properties"]["video_id"]["description"],
            "The ID of the YouTube video.",
        )

        deep_tool = tools_by_name["deep_check"]
        self.assertEqual(deep_tool.description, getdoc(fun_deep_check).splitlines()[0])
        self.assertEqual(
            deep_tool.params_json_schema["properties"]["text"]["description"],
            "The text to be checked.",
        )

        gdrive_tool = tools_by_name["google_drive_write_file"]
        self.assertEqual(gdrive_tool.description, getdoc(fun_write_file_to_google_drive).splitlines()[0])
        self.assertEqual(
            gdrive_tool.params_json_schema["properties"]["file_content"]["description"],
            "The content of the file to write.",
        )
        self.assertEqual(
            gdrive_tool.params_json_schema["properties"]["file_name"]["description"],
            "The name of the file in Google Drive.",
        )

    def test_agent_instructions_are_dedented(self):
        agent = build_agent(model="test")
        lines = [line for line in str(agent.instructions).splitlines() if line.strip()]
        self.assertTrue(lines)
        self.assertEqual(lines[0], "Generate transcript of YT video with video_id='123' and then pass it for deep analysis.")
