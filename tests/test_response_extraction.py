import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_refusal import ResponseOutputRefusal
from openai.types.responses.response_output_text import ResponseOutputText

from tool_context_relay.agent.handler import _assistant_text_from_output_items


class ResponseExtractionTests(unittest.TestCase):
    def test_extracts_assistant_output_text(self):
        msg = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(type="output_text", text="Hello", annotations=[], logprobs=None),
            ],
        )

        self.assertEqual(_assistant_text_from_output_items([msg]), "Hello")

    def test_concatenates_multiple_text_parts(self):
        msg = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(type="output_text", text="A", annotations=[], logprobs=None),
                ResponseOutputText(type="output_text", text="B", annotations=[], logprobs=None),
            ],
        )

        self.assertEqual(_assistant_text_from_output_items([msg]), "AB")

    def test_extracts_refusal_text(self):
        msg = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputRefusal(type="refusal", refusal="Nope"),
            ],
        )

        self.assertEqual(_assistant_text_from_output_items([msg]), "Nope")

    def test_skips_non_message_output_items(self):
        msg = ResponseOutputMessage(
            id="msg_1",
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(type="output_text", text="Hello", annotations=[], logprobs=None),
            ],
        )
        other = {"type": "function_call"}

        self.assertEqual(_assistant_text_from_output_items([other, msg]), "Hello")

