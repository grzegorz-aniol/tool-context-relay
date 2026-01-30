# tool-context-relay

Minimal CLI app that demonstrates OpenAI Agents SDK tool calls via hooks output.

## Setup

Requires `OPENAI_API_KEY` in the environment.

Install dependencies (needs network access):

`uv sync`

This project is configured as a uv package, so `uv sync` also installs the CLI and creates a
`tool-context-relay` wrapper in `.venv/bin`.

## Run

`tool-context-relay "Transcribe a YouTube video 123, then deep check it." --dump-context`

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
