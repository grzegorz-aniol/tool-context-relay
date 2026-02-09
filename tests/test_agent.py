import sys
import unittest
from inspect import getdoc
from pathlib import Path
import re
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent import build_agent
from tool_context_relay.tools.google_drive import fun_write_file_to_google_drive
from tool_context_relay.tools.mcp_deepcheck import fun_deep_check
from tool_context_relay.tools.mcp_email import fun_send_email
from tool_context_relay.tools.mcp_img_description import fun_get_img_description
from tool_context_relay.tools.mcp_page import fun_get_page
from tool_context_relay.tools.mcp_web_screenshot import fun_get_web_screenshot
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
    def test_agent_does_not_set_temperature_by_default(self):
        with patch("tool_context_relay.agent.agent.Agent") as agent_cls:
            build_agent(model="test", temperature=None)
            self.assertNotIn("model_settings", agent_cls.call_args.kwargs)

    def test_agent_sets_temperature_via_model_settings(self):
        from agents import ModelSettings

        with patch("tool_context_relay.agent.agent.Agent") as agent_cls:
            build_agent(model="test", temperature=0.3)
            settings = agent_cls.call_args.kwargs.get("model_settings")
            self.assertIsInstance(settings, ModelSettings)
            self.assertEqual(getattr(settings, "temperature", None), 0.3)

    def test_agent_tools_expose_underlying_docstrings(self):
        agent = build_agent(model="test")
        tools_by_name = {tool.name: tool for tool in agent.tools}

        test_cases = [
            ("yt_transcribe", fun_get_transcript),
            ("deep_check", fun_deep_check),
            ("google_drive_write_file", fun_write_file_to_google_drive),
            ("get_page", fun_get_page),
            ("send_email", fun_send_email),
            ("get_web_screenshot", fun_get_web_screenshot),
            ("get_img_description", fun_get_img_description),
        ]

        for tool_name, underlying_function in test_cases:
            with self.subTest(tool_name=tool_name):
                tool = tools_by_name[tool_name]
                underlying_doc = getdoc(underlying_function)
                assert underlying_doc is not None

                self.assertEqual(tool.description, underlying_doc.splitlines()[0])

                expected_arg_docs = extract_google_style_args_section(underlying_doc)

                tool_schema = tool.params_json_schema
                properties = tool_schema.get("properties", {})

                if not underlying_function.__code__.co_argcount:
                    self.assertFalse(expected_arg_docs)
                    self.assertFalse(properties)
                    continue

                self.assertTrue(expected_arg_docs, f"{underlying_function.__name__} must document Args:")
                self.assertEqual(set(properties.keys()), set(expected_arg_docs.keys()))

                for arg_name, arg_doc in expected_arg_docs.items():
                    self.assertIn("description", properties[arg_name])
                    self.assertEqual(properties[arg_name]["description"], arg_doc)

    def test_agent_instructions_are_dedented(self):
        agent = build_agent(model="test")
        lines = [line for line in str(agent.instructions).splitlines() if line.strip()]
        self.assertTrue(lines)
        self.assertEqual(lines[0], "- Be concise.")
        self.assertFalse(lines[0].startswith(" "))
