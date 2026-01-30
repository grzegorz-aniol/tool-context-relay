# tool-context-relay

Minimal CLI app that demonstrates OpenAI Agents SDK tool calls via hooks output.

## Setup

Requires an API key in the environment. Recommended variables:

- OpenAI (default): `OPENAI_API_KEY`
- OpenAI-compatible (`--endpoint ...` / `OPENAI_BASE_URL`): `OPENAI_COMPAT_API_KEY`

When using an OpenAI-compatible endpoint, `OPENAI_COMPAT_API_KEY` is mapped to
`OPENAI_API_KEY` internally for the SDKs.

Install dependencies (needs network access):

`uv sync`

This project is configured as a uv package, so `uv sync` also installs the CLI and creates a
`tool-context-relay` wrapper in `.venv/bin`.

## Run

`tool-context-relay "Transcribe a YouTube video 123, then deep check it." --dump-context`

Use a non-default OpenAI-compatible endpoint:

`tool-context-relay --provider openai-compat --endpoint http://localhost:11434/v1 "Transcribe 123"`

If you omit `--provider`, the default is `--provider auto` which chooses `openai-compat` when an endpoint override is present.

Color output:

- Auto (default): `tool-context-relay --color auto "..."` (colors only when stdout is a TTY)
- Always: `tool-context-relay --color always "..."` (useful when piping)
- Never: `tool-context-relay --color never "..."`

You can also control colors via env vars:

- Disable: `NO_COLOR=1` or `TOOL_CONTEXT_RELAY_NO_COLOR=1`
- Force: `FORCE_COLOR=1`

Seed initial context:

`tool-context-relay "Transcribe 123" --set name=Ada`

Run without syncing or activating a local venv:

`uv tool run --from . tool-context-relay "Transcribe 123" --set name=Ada`

## Codex MCP (project-scoped)

This repo includes a project-local Codex config at `.codex/config.toml` that points to a local MCP server:

- `http://127.0.0.1:64342/sse`
