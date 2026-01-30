import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.tools.google_drive import fun_write_file_to_google_drive


class GoogleDriveTests(unittest.TestCase):
    def test_fun_write_file_to_google_drive_returns_hex_id(self):
        file_id = fun_write_file_to_google_drive("hello", "greeting.txt")
        self.assertEqual(len(file_id), 32)
        int(file_id, 16)
