import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.agent.handler import RunHookHandler


class HookLoggingTests(unittest.TestCase):
    def test_emits_system_prompt_once_at_session_start(self):
        handler = RunHookHandler()
        input_items: list[object] = []

        with patch("tool_context_relay.agent.handler.emit_system") as emit_system:
            asyncio.run(handler.on_llm_start(None, None, "You are a helpful assistant.", input_items))
            asyncio.run(handler.on_llm_start(None, None, "You are a helpful assistant.", input_items))

        emit_system.assert_called_once_with("You are a helpful assistant.")

    def test_emits_user_messages_once_across_multiple_llm_calls(self):
        handler = RunHookHandler()
        input_items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Hello"}]},
        ]

        with patch("tool_context_relay.agent.handler.emit_user") as emit_user:
            asyncio.run(handler.on_llm_start(None, None, "SYSTEM", input_items))
            asyncio.run(handler.on_llm_start(None, None, "SYSTEM", input_items))

        emit_user.assert_called_once_with("Hello")

    def test_does_not_emit_system_prompt_via_user_emitter(self):
        handler = RunHookHandler()
        input_items: list[object] = []

        with patch("tool_context_relay.agent.handler.emit_user") as emit_user:
            asyncio.run(handler.on_llm_start(None, None, "You are a helpful assistant.", input_items))

        emit_user.assert_not_called()
