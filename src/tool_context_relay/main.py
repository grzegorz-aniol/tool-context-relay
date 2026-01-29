from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from agents import Agent, ModelResponse, RunContextWrapper, TContext, Tool, TResponseInputItem
from agents.lifecycle import RunHooksBase, TAgent
from dotenv import load_dotenv
load_dotenv(verbose=True)

from tool_context_relay.agent import build_agent
from tool_context_relay.context import RelayContext
from tool_context_relay.pretty import emit_tool_request, emit_tool_response, emit_user, emit_assistant


def _get_field(obj: object, key: str) -> object | None:
    if isinstance(obj, dict):
        # This helper supports both the strongly-typed SDK models and plain dicts
        # (e.g. when inspecting cached/serialized outputs).
        return obj.get(key)
    return getattr(obj, key, None)


def _assistant_text_from_output_items(output: Sequence[object]) -> str:
    chunks: list[str] = []

    for item in output:
        if _get_field(item, "type") != "message":
            continue
        if _get_field(item, "role") != "assistant":
            continue

        content = _get_field(item, "content")
        if not isinstance(content, Sequence):
            continue

        for part in content:
            part_type = _get_field(part, "type")
            if part_type == "output_text":
                text = _get_field(part, "text")
                if isinstance(text, str) and text:
                    chunks.append(text)
            elif part_type == "refusal":
                refusal = _get_field(part, "refusal")
                if isinstance(refusal, str) and refusal:
                    chunks.append(refusal)

    return "".join(chunks).strip()


class RunHookHandler(RunHooksBase[TContext, TAgent]):
    async def on_tool_start(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        tool: Tool,
    ) -> None:
        emit_tool_request(getattr(tool, "name", str(tool)))

    async def on_tool_end(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        tool: Tool,
        result: str,
    ) -> None:
        tool_name = getattr(tool, "name", str(tool))
        emit_tool_response(f"{tool_name} -> {result}")

    async def on_llm_start(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        system_prompt: Optional[str],
        input_items: list[TResponseInputItem],
    ) -> None:
        if system_prompt:
            emit_user(system_prompt)

    async def on_llm_end(
        self,
        context: RunContextWrapper[TContext],
        agent: TAgent,
        response: ModelResponse,
    ) -> None:
        assistant_text = _assistant_text_from_output_items(response.output)
        if assistant_text:
            emit_assistant(assistant_text)

def run_once(*, prompt: str, model: str, initial_kv: dict[str, str]) -> tuple[str, RelayContext]:
    from agents import Runner

    context = RelayContext(kv=dict(initial_kv))
    agent = build_agent(model=model)
    result = Runner.run_sync(agent, prompt, hooks=RunHookHandler(),  context=context)
    return result.final_output, context
