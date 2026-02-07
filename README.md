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
- If a tool result is **above the threshold**, the client activates the opaque-reference mechanism and returns an opaque reference (default `internal://...`).

Most importantly: **the client fully owns boxing/unboxing**. Real tools always receive and return real
values and do not need to know that opaque references exist. The only tools that deal with opaque references directly are the
**internal** “resolve” helpers (read / slice / length), which exist purely to let the model inspect underlying content when needed.

This repo is a minimal CLI demo of that idea using a few simulated tools (transcribe YouTube, deep-check text, write to Google Drive)
and prompt-case files that assert the expected pass-through behavior.

> The idea and its usage recommendations are also described in the companion article on my blog: https://appga.pl/


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

## Boxing strategies

Two boxing formats are supported:

- **Opaque (default):** tools return a plain `internal://<id>` string for large outputs.
- **JSON:** tools return a JSON string with a strict schema: `{"type":"resource_link","uri":"internal://<id>"}`.

You can choose the strategy via the CLI: `--boxing opaque` (default) or `--boxing json`.
The agent instructions/examples and internal resolve-tool descriptions are defined in code, keyed by boxing mode.

## Why this is useful

- **Stops context bloat** from large tool outputs (transcripts, web pages, big files, logs).
- **Reduces token costs** and improves stability (fewer “too long” failures, less noise).
- **Keeps tool pipelines ergonomic**: the model still calls tools the same way — it just passes `internal://...` around.
- **Works without server changes**: no tool-server modifications and no protocol changes are required — the relay is fully on the client side.

## When it’s not a good fit

- If you’re not seeing issues with long tool results (context bloat, costs, context limits).
- If your agent must deal with the full value in the prompt/context (summarization, extraction, classification, etc.). In that case, you can still use opaque references, but the model will need to use the client “resolve” tools for chunked reads (slice/length), or you may intentionally unbox and include the content.

## Examples (from prompt cases)

All prompts below come directly from `prompts/`.
The important part is that long data moves between tools as an opaque reference (default `internal://...`).

Prompt cases are Markdown files with YAML frontmatter. The frontmatter drives integration assertions:

- `tool_calls`: ordered list of expected tool calls; repeated `tool_name` entries mean multiple expected calls
- `opaque_id_input`: (per entry) expects the call to receive a previously returned `internal://...` id as an argument value
- `opaque_id_result`: (per entry) expects the call result to be an `internal://...` id
- `forbidden_tools`: tool names that must not be called
- `expect_internal_resolve`: whether `internal_resource_*` resolving calls are allowed/required

Prompt cases in this repo (what they test):

| Prompt Id | File                    | Description |
|----------:|-------------------------|-------------|
| 0         | `prompts/case0.md` | **No boxing**: uses `video_id='999'` which returns a short transcript in this demo, so it stays below the boxing threshold and no `internal://...` opaque id is used. |
| 1         | `prompts/case1.md` | **Box + pass-through**: transcript boxed to `internal://...` → `deep_check` gets opaque id unchanged (client unboxes internally). |
| 2         | `prompts/case2.md` | **Box + route**: transcript boxed → `google_drive_write_file` gets opaque id unchanged; `deep_check` must not be called. |
| 3         | `prompts/case3.md` | **Resolve only when needed (slice, not full read)**: boxed transcript → `deep_check`, then use **partial slicing** (`internal_resource_read_slice`) to answer a literal detail at the end (avoid full unboxing). |
| 4         | `prompts/case4.md` | **Mixed outputs**: boxed transcript → `deep_check`, then save transcript (opaque id) and analysis (plain text) to Drive. |

#### Example 0: short transcript → Deep Check (no boxing)

User prompt:

> Generate a transcript of the YouTube video with video_id='999' and then pass it to Deep Check for analysis.

Expected behavior:

1. `yt_transcribe(video_id="999")` returns a short transcript **as plain text** (not boxed)
2. `deep_check(text="<transcript>")` receives plain text (no `internal://...`)

#### Example 1: transcript → Deep Check (pass-through, no resolving)

User prompt:

> Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.

Expected behavior:

1. `yt_transcribe(video_id="123")` returns `internal://...` (boxed transcript)
2. `deep_check(text="internal://...")` receives the opaque reference unchanged (client unboxes internally)

#### Example 2: transcript → save to Google Drive (pass-through, no resolving)

User prompt:

> Generate a transcript of the YouTube video with video_id='123' and save it to a file on Google Drive named 'transcript.txt'.

Expected behavior:

1. `yt_transcribe(...)` returns `internal://...`
2. `google_drive_write_file(file_content="internal://...", file_name="transcript.txt")`

#### Example 3: transcript → Deep Check → user asks for a detail (resolve just enough)

User prompt:

> Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.
> Then let me know what number appears at the end of the transcript.

Expected behavior:

1. `yt_transcribe(...)` returns `internal://...`
2. `deep_check(text="internal://...")` (pass-through)
3. The model is allowed to resolve **only because the user asked for a literal detail**:
   it can call `internal_resource_read_slice(opaque_reference="internal://...", ...)` (or `internal_resource_read`) to inspect the ending.

#### Example 4: transcript → Deep Check → save both outputs (pass-through)

User prompt:

> Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.
> Then save both the transcript and the analysis to files on Google Drive named 'transcript.txt' and 'analysis.txt', respectively.

Intended behavior (the prompt asks for this):

1. `yt_transcribe(...)` returns `internal://...`
2. `deep_check(text="internal://...")` returns a short analysis string (in this demo it usually won’t be boxed)
3. `google_drive_write_file(file_content="internal://...", file_name="transcript.txt")`
4. `google_drive_write_file(file_content="<analysis>", file_name="analysis.txt")` (tools can accept either plain text or an opaque reference)

## Test results

I experimented with a few models to verify the concept. I tried both strong and older/weaker models, to see how well they follow the opaque ID handling instructions. I tested with a few additional few-shot examples (default CLI argument) and zero-shot prompts.

I tested Tool Context Relay with following models

### OpenAI GPT models

| Model       | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|-------------|-----------|----------------------------------------|----------|-----------------|
| gpt-4o-mini | 0         | No boxing                              | -        | ✅               |
| gpt-4o-mini | 1         | Box + pass-through → `deep_check`      | -        | ✅               |
| gpt-4o-mini | 2         | Box + route → Drive                    | -        | ❌               |
| gpt-4o-mini | 3         | Box + slice tail detail (no full read) | -        | ✅               |
| gpt-4o-mini | 4         | Box + `deep_check` + save both outputs | -        | ❌               |
| gpt-4o-mini | 0         | No boxing                              | ✔        | ✅               |
| gpt-4o-mini | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| gpt-4o-mini | 2         | Box + route → Drive                    | ✔        | ✅               |
| gpt-4o-mini | 3         | Box + slice tail detail (no full read) | ✔        | ✅               |
| gpt-4o-mini | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |
 

| Model       | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|-------------|-----------|----------------------------------------|----------|-----------------|
| gpt-4o      | 0         | No boxing                              | -        | ✅               |
| gpt-4o      | 1         | Box + pass-through → `deep_check`      | -        | ✅               |
| gpt-4o      | 2         | Box + route → Drive                    | -        | ✅               |
| gpt-4o      | 3         | Box + slice tail detail (no full read) | -        | ✅               |
| gpt-4o      | 4         | Box + `deep_check` + save both outputs | -        | ✅               |
| gpt-4o      | 0         | No boxing                              | ✔        | ✅               |
| gpt-4o      | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| gpt-4o      | 2         | Box + route → Drive                    | ✔        | ✅               |
| gpt-4o      | 3         | Box + slice tail detail (no full read) | ✔        | ✅               |
| gpt-4o      | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |
 

| Model   | Prompt Id  | Prompt (short)                         | Few-shot | Resolve success |
|---------|------------|----------------------------------------|----------|-----------------|
| gpt-5-mini | 0          | No boxing                              | -        | ✅               |
| gpt-5-mini | 1          | Box + pass-through → `deep_check`      | -        | ✅               |
| gpt-5-mini | 2          | Box + route → Drive                    | -        | ❌               |
| gpt-5-mini | 3          | Box + slice tail detail (no full read) | -        | ✅               |
| gpt-5-mini | 4          | Box + `deep_check` + save both outputs | -        | ✅               |
| gpt-5-mini | 0          | No boxing                              | ✔        | ✅               |
| gpt-5-mini | 1          | Box + pass-through → `deep_check`      | ✔        | ✅               |
| gpt-5-mini | 2          | Box + route → Drive                    | ✔        | ✅               |
| gpt-5-mini | 3          | Box + slice tail detail (no full read) | ✔        | ✅               |
| gpt-5-mini | 4          | Box + `deep_check` + save both outputs | ✔        | ✅               |


| Model   | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|---------|-----------|----------------------------------------|----------|-----------------|
| gpt-5.2 | 0         | No boxing                              | -        | ✅               |
| gpt-5.2 | 1         | Box + pass-through → `deep_check`      | -        | ✅               |
| gpt-5.2 | 2         | Box + route → Drive                    | -        | ✅               |
| gpt-5.2 | 3         | Box + slice tail detail (no full read) | -        | ✅               |
| gpt-5.2 | 4         | Box + `deep_check` + save both outputs | -        | ✅               |
| gpt-5.2 | 0         | No boxing                              | ✔        | ✅               |
| gpt-5.2 | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| gpt-5.2 | 2         | Box + route → Drive                    | ✔        | ✅               |
| gpt-5.2 | 3         | Box + slice tail detail (no full read) | ✔        | ✅               |
| gpt-5.2 | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |

### Qwen 3 model

#### Boxing method: opaque ID (default)

 | Model        | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|--------------|-----------|----------------------------------------|----------|-----------------|
| qwen-3b:Q8_0 | 0         | No boxing                              | -        | ✅               |
| qwen-3b:Q8_0 | 1         | Box + pass-through → `deep_check`      | -        | ❌               |
| qwen-3b:Q8_0 | 2         | Box + route → Drive                    | -        | ✅               |
| qwen-3b:Q8_0 | 3         | Box + slice tail detail (no full read) | -        | ❌               |
| qwen-3b:Q8_0 | 4         | Box + `deep_check` + save both outputs | -        | ❌               |
| qwen-3b:Q8_0 | 0         | No boxing                              | ✔        | ✅               |
| qwen-3b:Q8_0 | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| qwen-3b:Q8_0 | 2         | Box + route → Drive                    | ✔        | ✅               |
| qwen-3b:Q8_0 | 3         | Box + slice tail detail (no full read) | ✔        | ✅               |
| qwen-3b:Q8_0 | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |

#### Boxing method: JSON

 | Model        | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|--------------|-----------|----------------------------------------|----------|-----------------|
| qwen-3b:Q8_0 | 0         | No boxing                              | -        | ✅               |
| qwen-3b:Q8_0 | 1         | Box + pass-through → `deep_check`      | -        | ❌               |
| qwen-3b:Q8_0 | 2         | Box + route → Drive                    | -        | ❌               |
| qwen-3b:Q8_0 | 3         | Box + slice tail detail (no full read) | -        | ✅               |
| qwen-3b:Q8_0 | 4         | Box + `deep_check` + save both outputs | -        | ❌               |
| qwen-3b:Q8_0 | 0         | No boxing                              | ✔        | ✅               |
| qwen-3b:Q8_0 | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| qwen-3b:Q8_0 | 2         | Box + route → Drive                    | ✔        | ✅               |
| qwen-3b:Q8_0 | 3         | Box + slice tail detail (no full read) | ✔        | ❌               |
| qwen-3b:Q8_0 | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |

### Bielik v3 model


 | Model              | Prompt Id | Prompt (short)                         | Few-shot | Resolve success |
|--------------------|-----------|----------------------------------------|----------|-----------------|
| Bielik-11b-v3:Q8_0 | 0         | No boxing                              | -        | ✅               |
| Bielik-11b-v3:Q8_0 | 1         | Box + pass-through → `deep_check`      | -        | ✅               |
| Bielik-11b-v3:Q8_0 | 2         | Box + route → Drive                    | -        | ✅               |
| Bielik-11b-v3:Q8_0 | 3         | Box + slice tail detail (no full read) | -        | ❌               |
| Bielik-11b-v3:Q8_0 | 4         | Box + `deep_check` + save both outputs | -        | ✅               |
| Bielik-11b-v3:Q8_0 | 0         | No boxing                              | ✔        | ✅               |
| Bielik-11b-v3:Q8_0 | 1         | Box + pass-through → `deep_check`      | ✔        | ✅               |
| Bielik-11b-v3:Q8_0 | 2         | Box + route → Drive                    | ✔        | ✅               |
| Bielik-11b-v3:Q8_0 | 3         | Box + slice tail detail (no full read) | ✔        | ✅               |
| Bielik-11b-v3:Q8_0 | 4         | Box + `deep_check` + save both outputs | ✔        | ✅               |

## Conclusion (based on test results)

Based on the tables above (limited experiments):

- Flagship models like `gpt-4o` and `gpt-5.2` were reliable even without few-shot examples, so a strong “training-style” system prompt may not be strictly required for them in practice.
- Weaker/smaller models (especially `*-mini` and `qwen-3b`) were noticeably less consistent without extra guidance; for these, few-shot examples improved reliability across all models, especially for the weaker ones.
- Overall, the Tool Context Relay pattern worked well across all tested models when few-shot examples were provided, demonstrating its effectiveness in managing long tool outputs without overwhelming the model's context. 
- Few-shot examples likely won’t be necessary for weaker models after fine-tuning on similar tasks, but that’s outside the scope of this demo.

---

## Technical details

### Setup

Requires **Python 3.14+**.

`tool-context-relay` discovers credentials via **profiles**. Each profile is identified by a case-insensitive name
and looks for env vars that share that name as a prefix (e.g. prefix `OPENAI` looks for `OPENAI_API_KEY`, `OPENAI_MODEL`,
`OPENAI_BASE_URL`, `OPENAI_PROVIDER`, etc.). The CLI defaults to profile `openai` unless you pass `--profile` or set
`TOOL_CONTEXT_RELAY_PROFILE`. In practice you can wire up multiple profiles in a single `.env` file and switch between them.

`.env.example` lists the placeholders you can fill for the built-in profiles (openai, bielik, qwen). A minimal setup may look like:

```sh
OPENAI_API_KEY="sk-your-openai-key"
OPENAI_MODEL="gpt-4.1-mini"

BIELIK_PROVIDER="openai-compat"
BIELIK_API_KEY="sk-your-bielik-key"
BIELIK_BASE_URL="http://127.0.0.1:1234/v1"
BIELIK_MODEL="speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"

QWEN_PROVIDER="openai-compat"
QWEN_API_KEY="sk-your-qwen-key"
QWEN_BASE_URL="http://127.0.0.1:1234/v1"
QWEN_MODEL="Qwen/Qwen3-8B-GGUF:Q8_0"
```

When a profile does not specify `*_PROVIDER`, it defaults to using the `openai` provider definition. `*_PROVIDER` now simply names the provider (e.g. `openrouter`, `llamacpp`, `openai`) so you can configure each target once and have every profile reuse it. You can optionally pin which downstream backend should run the requested model by setting `<PREFIX>_BACKEND_PROVIDER` (for example `OPENROUTER_BACKEND_PROVIDER=anthropic`). The `openrouter` provider always receives `provider.allow_fallbacks=false` plus `provider.data_collection=deny` so it never falls back to OpenAI nor collects telemetry.

Install dependencies (needs network access):

`uv sync`

Install dependencies (needs network access):

`uv sync`

This project is configured as a uv package, so `uv sync` also installs the CLI and creates a `tool-context-relay` wrapper in `.venv/bin`.

### Run

Run once with a prompt:

`tool-context-relay "Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis."`

Run from a prompt-case file (Markdown). If the file starts with YAML frontmatter, the CLI validates tool-call behavior
against that metadata; if there is no frontmatter, it just executes the prompt:

`tool-context-relay --file prompts/case1.md`

Run multiple files via a wildcard pattern:

`tool-context-relay --glob "prompts/*.md"`

Dump final context as JSON to stdout:

`tool-context-relay "..." --dump-context`

Print tool definitions (name/description/arg schema) before running:

`tool-context-relay "..." --print-tools`

Hide the agent system instruction output (it is shown by default):

`tool-context-relay --no-show-system-instruction "..."`

Use a specific profile (and its env vars):

`tool-context-relay --profile bielik --model BIELIK "Generate ..."`

Profiles map to <PREFIX>_API_KEY, <PREFIX>_MODEL, and so on, and you can also set `<PREFIX>_TEMPERATURE` (for example `BIELIK_TEMPERATURE=0.1`) to provide a profile-specific default; `--temperature` overrides that value.

Set `TOOL_CONTEXT_RELAY_PROFILE=bielik` to make a profile the default for your shell/session.

`--model` remains available to override the profile’s default model; omit it to rely on the profile default (or the fallback `gpt-4.1-mini`).

Set sampling temperature (non-reasoning models only):

`tool-context-relay --temperature 0.1 "..."` (ignored for reasoning models like `gpt-5*`)

Profile-level `<PREFIX>_TEMPERATURE` variables are also supported (e.g., `BIELIK_TEMPERATURE=0.1`), but CLI arguments win and reasoning models ignore the sampling temperature entirely.

Control request retries:

`tool-context-relay --max-retries 6 "..."` (overrides the built-in OpenAI client retry count; use `0` to disable).

Select boxing strategy for large tool outputs:

`tool-context-relay --boxing opaque "..."` (default)

`tool-context-relay --boxing json "..."` (returns JSON string `{"type":"resource_link","uri":"internal://<id>"}`)

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

### Notes

`tool-context-relay` loads environment variables from a local `.env` file (if present) via `python-dotenv`.
