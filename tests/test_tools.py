import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.tools.tool_relay import tool_relay, unbox_value, box_value, is_resource_id
from tool_context_relay.tools.mcp_yt import fun_get_transcript
from tool_context_relay.tools.mcp_page import fun_get_page, SMALL_PAGE_URL, LARGE_PAGE_URL
from tool_context_relay.tools.mcp_email import fun_send_email
from tool_context_relay.tools.mcp_web_screenshot import fun_get_web_screenshot
from tool_context_relay.tools.mcp_img_description import (
    fun_get_img_description,
    IMAGE_URL_CAT,
    IMAGE_URL_DESK,
    IMAGE_URL_MOUNTAIN,
)


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
        self.assertEqual(unbox_value(resource_id), "x" * 2048)

    def test_tool_relay_resource_id_never_contains_negative_sign(self):
        def big(value: str) -> str:
            return value * 2048

        with patch("builtins.hash", return_value=-1):
            resource_id = tool_relay(big, ["x"])

        self.assertTrue(resource_id.startswith("internal://"))
        self.assertNotIn("-", resource_id)
        self.assertEqual(unbox_value(resource_id), "x" * 2048)

    def test_fun_get_transcript_returns_short_value_for_special_id(self):
        self.assertEqual(fun_get_transcript("999"), "Welcome in a new episode and good bye")

    def test_box_value_json_mode_returns_resource_link_string(self):
        value = "x" * 2048
        boxed = box_value(value, mode="json")
        self.assertIsInstance(boxed, str)
        self.assertIn('"type":"resource_link"', boxed)
        self.assertTrue(is_resource_id(boxed))
        self.assertEqual(unbox_value(boxed), value)

    def test_fun_get_page_returns_small_html_for_small_url(self):
        page = fun_get_page(SMALL_PAGE_URL)
        self.assertIn("<title>Demo Small Page</title>", page)
        self.assertLess(len(page), 256)

    def test_fun_get_page_returns_large_html_for_large_url(self):
        page = fun_get_page(LARGE_PAGE_URL)
        self.assertIn("<title>Demo Large Page</title>", page)
        self.assertGreater(len(page), 256)
        self.assertLessEqual(len(page), 3000)

    def test_fun_send_email_returns_confirmation(self):
        result = fun_send_email("hello@example.com", "Test body")
        self.assertIn("Email sent to 'hello@example.com'", result)
        self.assertIn("Body length=9", result)

    def test_fun_get_web_screenshot_returns_base64(self):
        result = fun_get_web_screenshot()
        self.assertTrue(result)
        self.assertLessEqual(len(result), 2000)

    def test_fun_get_img_description_returns_two_sentences(self):
        for url in (IMAGE_URL_CAT, IMAGE_URL_DESK, IMAGE_URL_MOUNTAIN):
            with self.subTest(url=url):
                result = fun_get_img_description(url)
                self.assertEqual(result.count("."), 2)
