import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.pretty import emit_assistant, emit_default, emit_tool_request, emit_tool_response, emit_user


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:  # noqa: D401 - tiny helper
        return True


class PrettyTests(unittest.TestCase):
    def test_prefix_is_preceded_by_blank_line(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"TOOL_CONTEXT_RELAY_COLOR": "never"}, clear=True):
            emit_user("hello", stream=stream, width=120)
        self.assertTrue(stream.getvalue().startswith("\n<user>\nhello\n"))

    def test_wraps_to_width(self):
        stream = io.StringIO()
        long_text = " ".join(["word"] * 50)
        emit_user(long_text, stream=stream, width=40)
        out = stream.getvalue().rstrip("\n")
        for line in out.splitlines():
            if line in {"", "<user>"}:
                continue
            self.assertLessEqual(len(line), 40)

    def test_colors_enabled_on_tty(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {}, clear=True):
            emit_tool_request("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertTrue(out.startswith("\n\x1b[36m<tool call>\x1b[0m\n\x1b[36mhello\x1b[0m\n"))

    def test_user_is_light_yellow_on_tty(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {}, clear=True):
            emit_user("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertTrue(out.startswith("\n\x1b[38;5;229m<user>\x1b[0m\n\x1b[38;5;229mhello\x1b[0m\n"))

    def test_tool_result_is_green_on_tty(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {}, clear=True):
            emit_tool_response("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertTrue(out.startswith("\n\x1b[32m<tool result>\x1b[0m\n\x1b[32mhello\x1b[0m\n"))

    def test_no_color_disables_colors(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
            emit_assistant("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertNotIn("\x1b[", out)

    def test_force_color_enables_without_tty(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=True):
            emit_tool_request("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertTrue(out.startswith("\n\x1b[36m<tool call>\x1b[0m\n\x1b[36mhello\x1b[0m\n"))

    def test_color_mode_never_disables_on_tty(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {"TOOL_CONTEXT_RELAY_COLOR": "never"}, clear=True):
            emit_assistant("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertNotIn("\x1b[", out)

    def test_term_dumb_disables_on_tty_in_auto_mode(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
            emit_assistant("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertNotIn("\x1b[", out)

    def test_tool_result_multiline_is_single_event(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"TOOL_CONTEXT_RELAY_COLOR": "never"}, clear=True):
            emit_tool_response("line1\nline2", stream=stream, width=120)
        out = stream.getvalue()
        self.assertEqual(out.count("<tool result>"), 1)
        self.assertIn("\n<tool result>\nline1\nline2\n", out)

    def test_default_group_combines_without_empty_lines(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"TOOL_CONTEXT_RELAY_COLOR": "never"}, clear=True):
            emit_default("Fetching transcript for video ID: 123", group="fun_get_transcript", stream=stream, width=120)
            emit_default(
                "Transcript generated. Length: 1800, Starting: 'For a long time, YouTube has b...'",
                group="fun_get_transcript",
                stream=stream,
                width=120,
            )
        out = stream.getvalue()
        self.assertEqual(out.count("fun_get_transcript:"), 1)
        self.assertIn(
            "\nfun_get_transcript:\n"
            "Fetching transcript for video ID: 123\n"
            "Transcript generated. Length: 1800, Starting: 'For a long time, YouTube has b...'\n",
            out,
        )
