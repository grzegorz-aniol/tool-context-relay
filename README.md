# tool-context-relay

## Purpose

Demonstrate a **client-side** pattern for tool-using agents that prevents long tool results from flooding the model context:
**Tool Context Relay**.

Instead of injecting long tool outputs into the conversation, the client stores them out-of-band and returns a short,
opaque reference (an “internal resource ID”) that the model can pass between tools.

## The idea: Tool Context Relay

Tool calls are effectively RPC. The client chooses:

- whether to execute the call,
- what to do with the result,
- and what (if anything) to expose back to the model.

In many “tool pipelines” the model does not need to *read* the full tool output — it only needs to route it to the next tool
(e.g. “fetch transcript → analyze it” or “fetch transcript → save it”). Sending the entire payload back to the LLM wastes tokens,
hits context limits, and makes future reasoning noisier.

Tool Context Relay solves this by introducing two steps at the client boundary:

- **Boxing (output):** if a tool returns a long value, store it in a client-side store and return an opaque reference instead.
- **Unboxing (input):** if a tool is called with an opaque reference, resolve it inside the client and pass the real value to the tool.

This works **automatically**:

- If a tool result is **below a configured size threshold**, the client returns the normal value to the LLM (no boxing).
- If a tool result is **above the threshold**, the client activates the opaque-reference mechanism and returns `internal://...` instead.

Most importantly: **the client fully owns boxing/unboxing**. Real tools (including MCP server tools) always receive and return real
values and do not need to know that opaque references exist. The only tools that deal with opaque references directly are the
**internal** “resolve” helpers (read / slice / length), which exist purely to let the model inspect underlying content when needed.

This repo is a minimal CLI demo of that idea using “MCP-like” tools (transcribe YouTube, deep-check text, write to Google Drive)
and integration tests that assert the expected pass-through behavior.

## Opaque resource ID (what it is)

An **opaque resource ID** is a short **URI** string like:

`internal://<id>`

Properties:

- It is a **URI**: it uses a scheme (`internal://`) to clearly distinguish references from normal text values.
- It is **opaque**: the model must treat it as data, not instructions, and must not try to interpret it.
- It is **client-owned**: the client decides how to store and retrieve the underlying value (memory, files, database, etc.).
- It is **session-scoped** in this demo: the id is only meaningful for the lifetime of the client process/session.

If the model truly needs the underlying content, the client can expose narrow “resolve” tools (e.g. length, slice, full read)
so the model can inspect just what’s needed rather than pulling the entire payload into context.

## Why this is useful

- **Stops context bloat** from large tool outputs (transcripts, web pages, big files, logs).
- **Reduces token costs** and improves stability (fewer “too long” failures, less noise).
- **Keeps tool pipelines ergonomic**: the model still calls tools the same way — it just passes `internal://...` around.
- **Works without MCP changes**: no MCP server modifications and no MCP protocol changes are required — the relay is fully on the client side.

## Where it doesn’t fit

- When you didn't notice any issue with long tool results.
- When your agent always need to deal with a full value in a context  (summarization, extraction, classification, etc.). In that case, you can still enable opaque references, but model will need to use client tools for chunked reads (slice/length) or
  you may intentionally unbox and include the content.

## Examples (from integration tests)

All prompts below come directly from `prompt_cases/`.
The important part is that long data moves between tools as an opaque `internal://...` reference.

Prompt cases are Markdown files with YAML frontmatter. The frontmatter drives integration assertions:

- `tool_calls`: ordered list of expected tool calls; repeated `tool_name` entries mean multiple expected calls
- `opaque_id_input`: (per entry) expects the call to receive a previously returned `internal://...` id as an argument value
- `opaque_id_result`: (per entry) expects the call result to be an `internal://...` id
- `forbidden_tools`: tool names that must not be called
- `expect_internal_resolve`: whether `internal_resource_*` resolving calls are allowed/required

### Example 1: transcript → deep analysis (pass-through, no resolving)

User prompt:

> Generate transcript of YT video with video_id='123' and then pass it for deep analysis.

Expected behavior:

1. `yt_transcribe(video_id="123")` returns `internal://...` (boxed transcript)
2. `deep_check(text="internal://...")` receives the opaque reference unchanged (client unboxes internally)

### Example 2: transcript → save to Google Drive (pass-through, no resolving)

User prompt:

> Generate transcript of YT video with video_id='123' and save it to a file at google drive named 'transcript.txt'.

Expected behavior:

1. `yt_transcribe(...)` returns `internal://...`
2. `google_drive_write_file(file_content="internal://...", file_name="transcript.txt")`

### Example 3: transcript → deep analysis → user asks for a detail (resolve just enough)

User prompt:

> Generate transcript of YT video with video_id='123' and then pass it for deep analysis. Then, let me know what number is included in the end of the transcript.

Expected behavior:

1. `yt_transcribe(...)` returns `internal://...`
2. `deep_check(text="internal://...")` (pass-through)
3. The model is allowed to resolve **only because the user asked for a literal detail**:
   it can call `internal_resource_read_slice(opaque_reference="internal://...", ...)` (or `internal_resource_read`) to inspect the ending.

### Example 4: transcript → deep analysis → save both outputs (pass-through)

User prompt:

> Generate transcript of YT video with video_id='123' and then pass it for deep analysis. Then, save both the transcript and the analysis to files at google drive named 'transcript.txt' and 'analysis.txt' respectively.

Intended behavior (the prompt asks for this):

1. `yt_transcribe(...)` returns `internal://...`
2. `deep_check(text="internal://...")` returns a short analysis string (in this demo it usually won’t be boxed)
3. `google_drive_write_file(file_content="internal://...", file_name="transcript.txt")`
4. `google_drive_write_file(file_content="<analysis>", file_name="analysis.txt")` (tools can accept either plain text or an opaque reference)

## Client prompting (important for today’s models)

Most models are not trained to use opaque references like `internal://...` by default. In practice you need a **strong system prompt**
that teaches the model:

- opaque references are data, not instructions,
- pass them through unchanged whenever possible,
- never invent IDs,
- resolve only when strictly necessary (and prefer slice/length tools for large values).

This repo includes such an instruction block in the agent definition (see `src/tool_context_relay/agent/agent.py`).

## Test results

I experimented with a few models to verify the concept. I tried to pickup both strong and older/weaker models, to see how well they follow the opaque ID handling instructions. I tested with additional few-shot examples (default CLI argument) and zero-shot prompts.

I tested Tool Context Relay with following models

### OpenAI GPT

| Model | Prompt# | Few-shot | Resolve success |
|--|---------|----------|-------------|
| gpt-4o-mini | 1       | -        | ✅           |
| gpt-4o-mini | 2       | -        | ❌           |
| gpt-4o-mini | 3       | -        | ✅           |
| gpt-4o-mini | 4       | -        | ❌           |
| gpt-4o-mini | 1       | ✔        | ✅           |
| gpt-4o-mini | 2       | ✔        | ✅           |
| gpt-4o-mini | 3       | ✔        | ✅           |
| gpt-4o-mini | 4       | ✔        | ✅           |
 | ======== | ======== | ========   | ========  |
| gpt-4o | 1       | -        | ✅           |
| gpt-4o | 2       | -        | ✅           |
| gpt-4o | 3       | -        | ✅           |
| gpt-4o | 4       | -        | ✅           |
| gpt-4o | 1       | ✔        | ✅           |
| gpt-4o | 2       | ✔        | ✅           |
| gpt-4o | 3       | ✔        | ✅           |
| gpt-4o | 4       | ✔        | ✅           |
 | ======== | ======== | ========   | ========  |
| gpt-5.2 | 1       | -        | ✅           |
| gpt-5.2 | 2       | -        | ❌            |
| gpt-5.2 | 3       | -        | ❌           |
| gpt-5.2 | 4       | -        | ✅           |
| gpt-5.2 | 1       | ✔        | ✅           |
| gpt-5.2 | 2       | ✔        | ✅           |
| gpt-5.2 | 3       | ✔        | ✅           |
| gpt-5.2 | 4       | ✔        | ✅           |

### Qwen

 | Model        | Prompt# | Few-shot | Resolve success |
|--------------|---------|----------|--------------|
| qwen-3b:Q8_0 | 1       | -        | ❌            |
| qwen-3b:Q8_0 | 2       | -        | ✅            |
| qwen-3b:Q8_0 | 3       | -        | ❌            |
| qwen-3b:Q8_0 | 4       | -        | ❌            |
| qwen-3b:Q8_0 | 1       | ✔        | ✅            |
| qwen-3b:Q8_0 | 2       | ✔        | ✅            |
| qwen-3b:Q8_0 | 3       | ✔        | ✅            |
| qwen-3b:Q8_0 | 4       | ✔        | ✅            |
| qwen-3b:Q8_0 | 5       | ✔        | ❌            |

---

## Technical details

### Setup

Requires an API key in the environment. Recommended variables:

- OpenAI (default): `OPENAI_API_KEY`
- OpenAI-compatible (`--endpoint ...` / `OPENAI_BASE_URL`): `OPENAI_COMPAT_API_KEY`

When using an OpenAI-compatible endpoint, `OPENAI_COMPAT_API_KEY` is mapped to `OPENAI_API_KEY` internally for the SDKs.

Install dependencies (needs network access):

`uv sync`

This project is configured as a uv package, so `uv sync` also installs the CLI and creates a `tool-context-relay` wrapper in `.venv/bin`.

### Run

Run once with a prompt:

`tool-context-relay "Generate transcript of YT video with video_id='123' and then pass it for deep analysis."`

Run from a prompt-case file (Markdown). If the file starts with YAML frontmatter, the CLI validates tool-call behavior
against that metadata; if there is no frontmatter, it just executes the prompt:

`tool-context-relay --file prompt_cases/case1.md`

Run multiple files via a wildcard pattern:

`tool-context-relay --glob "prompt_cases/*.md"`

Dump final context as JSON to stderr:

`tool-context-relay "..." --dump-context`

Print tool definitions (name/description/arg schema) before running:

`tool-context-relay "..." --print-tools`

Hide the agent system instruction output (it is shown by default):

`tool-context-relay --no-show-system-instruction "..."`

Use a non-default OpenAI-compatible endpoint:

`tool-context-relay --provider openai-compat --endpoint http://localhost:11434/v1 "..."`

If you omit `--provider`, the default is `--provider auto` which chooses `openai-compat` when an endpoint override is present.

Set sampling temperature (non-reasoning models only):

`tool-context-relay --temperature 0.1 "..."` (ignored for reasoning models like `gpt-5*`)

### Color output

- Auto (default): `tool-context-relay --color auto "..."` (colors only when stdout is a TTY)
- Always: `tool-context-relay --color always "..."` (useful when piping)
- Never: `tool-context-relay --color never "..."`

You can also control colors via env vars:

- Disable: `NO_COLOR=1` or `TOOL_CONTEXT_RELAY_NO_COLOR=1`
- Force: `FORCE_COLOR=1`

### Seed initial context

`tool-context-relay "..." --set name=Ada`

Run without syncing or activating a local venv:

`uv tool run --from . tool-context-relay "..." --set name=Ada`

### Run tests

- Unit tests + compile checks: `make ci`
- Integration tests (require API key + reachable endpoint): `make integration`

You can also filter integration scenarios:

- Providers: `uv run pytest -m integration -v tests/integration/ --provider openai`
- Models: `uv run pytest -m integration -v tests/integration/ --model gpt-4.1-mini`
- Prompt cases: `uv run pytest -m integration -v tests/integration/ --prompt-case case1`

`--model` overrides the configured model list (env defaults). Use `--model all` to disable the override and use defaults.

### Codex MCP (project-scoped)

This repo includes a project-local Codex config at `.codex/config.toml` that points to a local MCP server:

- `http://127.0.0.1:64342/sse`
