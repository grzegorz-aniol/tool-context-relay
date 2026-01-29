# tool-context-relay

Minimal CLI app that demonstrates OpenAI Agents SDK tool calls via hooks output.

## Setup

Requires `OPENAI_API_KEY` in the environment.

Install dependencies (needs network access):

`uv sync --dev`

## Run

`tool-context-relay "Transcribe a YouTube video 123, then deep check it." --dump-context`

Seed initial context:

`tool-context-relay "Transcribe 123" --set name=Ada`
