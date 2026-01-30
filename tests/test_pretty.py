import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.pretty import emit_assistant, emit_tool_request, emit_user


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:  # noqa: D401 - tiny helper
        return True


class PrettyTests(unittest.TestCase):
    def test_wraps_to_width(self):
        stream = io.StringIO()
        long_text = " ".join(["word"] * 50)
        emit_user(long_text, stream=stream, width=40)
        out = stream.getvalue().rstrip("\n")
        for line in out.splitlines():
            self.assertLessEqual(len(line), 40)

    def test_colors_enabled_on_tty(self):
        stream = _TtyStringIO()
        with patch.dict(os.environ, {}, clear=True):
            emit_tool_request("hello", stream=stream, width=120)
        out = stream.getvalue()
        self.assertTrue(out.startswith("\x1b[33m"))
        self.assertTrue(out.endswith("\x1b[0m\n"))

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
        self.assertTrue(out.startswith("\x1b[33m"))
        self.assertTrue(out.endswith("\x1b[0m\n"))

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
