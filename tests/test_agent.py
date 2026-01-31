import sys
import unittest
from inspect import getdoc
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent import build_agent
from tool_context_relay.tools.google_drive import fun_write_file_to_google_drive
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_yt import fun_get_transcript


def extract_google_style_args_section(doc: str) -> dict[str, str]:
    lines = doc.splitlines()
    try:
        args_index = next(i for i, line in enumerate(lines) if line.strip() == "Args:")
    except StopIteration:
        return {}

    docs_by_arg: dict[str, str] = {}
    current_arg: str | None = None

    for line in lines[args_index + 1:]:
        if line and not line.startswith(" "):
            break

        match = re.match(r"^\s{4}(\w+)\s*(?:\([^)]*\))?:\s*(.+?)\s*$", line)
        if match:
            current_arg = match.group(1)
            docs_by_arg[current_arg] = match.group(2)
            continue

        if current_arg is not None and line.strip():
            docs_by_arg[current_arg] = f"{docs_by_arg[current_arg]} {line.strip()}"

    return docs_by_arg


class AgentTests(unittest.TestCase):
    def test_agent_tools_expose_underlying_docstrings(self):
        agent = build_agent(model="test")
        tools_by_name = {tool.name: tool for tool in agent.tools}

        test_cases = [
            ("yt_transcribe", fun_get_transcript),
            ("deep_check", fun_deep_check),
            ("google_drive_write_file", fun_write_file_to_google_drive),
        ]

        for tool_name, underlying_function in test_cases:
            with self.subTest(tool_name=tool_name):
                tool = tools_by_name[tool_name]
                underlying_doc = getdoc(underlying_function)
                assert underlying_doc is not None

                self.assertEqual(tool.description, underlying_doc.splitlines()[0])

                expected_arg_docs = extract_google_style_args_section(underlying_doc)
                self.assertTrue(expected_arg_docs, f"{underlying_function.__name__} must document Args:")

                tool_schema = tool.params_json_schema
                properties = tool_schema.get("properties", {})

                self.assertEqual(set(properties.keys()), set(expected_arg_docs.keys()))

                for arg_name, arg_doc in expected_arg_docs.items():
                    self.assertIn("description", properties[arg_name])
                    self.assertEqual(properties[arg_name]["description"], arg_doc)

    def test_agent_instructions_are_dedented(self):
        agent = build_agent(model="test")
        lines = [line for line in str(agent.instructions).splitlines() if line.strip()]
        self.assertTrue(lines)
        self.assertEqual(lines[0], "Generate transcript of YT video with video_id='123' and then pass it for deep analysis.")
