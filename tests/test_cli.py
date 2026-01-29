import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.cli import _parse_kv, main


class CliTests(unittest.TestCase):
    def test_parse_kv_ok(self):
        self.assertEqual(_parse_kv(["a=1", "b=two=2"]), {"a": "1", "b": "two=2"})

    def test_parse_kv_invalid(self):
        for pairs in (["nope"], ["=x"], [""]):
            with self.assertRaises(ValueError):
                _parse_kv(pairs)

    def test_main_rejects_empty_prompt(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([""])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Prompt must not be empty.", stderr.getvalue())

    def test_main_rejects_whitespace_prompt(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["   "])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Prompt must not be empty.", stderr.getvalue())
