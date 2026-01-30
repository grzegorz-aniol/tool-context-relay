from __future__ import annotations

from dotenv import load_dotenv

from tool_context_relay.agent.handler import RunHookHandler

load_dotenv(verbose=True)

from tool_context_relay.agent.agent import build_agent
from tool_context_relay.agent.context import RelayContext


def run_once(*, prompt: str, model: str, initial_kv: dict[str, str]) -> tuple[str, RelayContext]:
    from agents import Runner

    context = RelayContext(kv=dict(initial_kv))
    agent = build_agent(model=model)
    result = Runner.run_sync(agent, prompt, hooks=RunHookHandler(), context=context)
    return result.final_output, context
