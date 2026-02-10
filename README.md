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

This repo is a minimal CLI PoC of that idea using a few simulated tools (transcribe YouTube, deep-check text, write to Google Drive)
and prompt-case files that assert the expected pass-through behavior.

> The idea and its usage recommendations are also described in the companion [article on my blog](https://appga.pl/2026/02/07/tool-context-relay-how-not-to-flood-the-context-with-long-tool-result/)


## Opaque reference (what it is)

An **opaque reference** is a short **URI** string like:

`internal://<id>`

Properties:

- It is a **URI**: it uses a scheme (`internal://`) to clearly distinguish references from normal text values.
- It is **opaque**: the model must treat it as data, not instructions, and must not try to interpret it.
- It is **client-owned**: the client decides how to store and retrieve the underlying value (memory, files, database, etc.).
- It is **session-scoped** in this PoC: the id is only meaningful for the lifetime of the client process/session.

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
  - `allow_multiple`: (per entry) if true, validation switches to counts (order-agnostic); tools with this flag are allowed to run more times than listed
- `opaque_id_input`: (per entry) expects the call to receive a previously returned `internal://...` opaque reference as an argument value
- `opaque_id_result`: (per entry) expects the call result to be an `internal://...` opaque reference
- `forbidden_tools`: tool names that must not be called
  - Use this to block full reads (e.g., forbid `internal_resource_read`) or to require specific internal tools.

Prompt cases in this repo (what they test):

| Prompt Id | File                    | Description |
|----------:|-------------------------|-------------|
| 0         | `prompts/case0.md` | **No boxing**: uses `video_id='999'` which returns a short transcript in this PoC, so it stays below the boxing threshold and no `internal://...` opaque reference is used. |
| 1         | `prompts/case1.md` | **Box + pass-through**: transcript boxed to `internal://...` → `deep_check` gets opaque reference unchanged (client unboxes internally). |
| 2         | `prompts/case2.md` | **Box + route**: transcript boxed → `google_drive_write_file` gets opaque reference unchanged; `deep_check` must not be called. |
| 3         | `prompts/case3.md` | **Resolve only when needed (slice, not full read)**: boxed transcript → `deep_check`, then require **partial slicing** (`internal_resource_read_slice`) to answer a literal detail at the end (full read is forbidden). |
| 4         | `prompts/case4.md` | **Mixed outputs**: boxed transcript → `deep_check`, then save transcript (opaque reference) and analysis (plain text) to Drive. |
| web1      | `prompts/web1.md` | **Web page grep**: fetch a large HTML page (`get_page` boxed), then locate image elements via `internal_resource_grep` without full reads. |

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
   it must call `internal_resource_read_slice(opaque_reference="internal://...", ...)` to inspect the ending (full read is forbidden).

#### Example 4: transcript → Deep Check → save both outputs (pass-through)

User prompt:

> Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.
> Then save both the transcript and the analysis to files on Google Drive named 'transcript.txt' and 'analysis.txt', respectively.

Intended behavior (the prompt asks for this):

1. `yt_transcribe(...)` returns `internal://...`
2. `deep_check(text="internal://...")` returns a short analysis string (in this PoC it usually won’t be boxed)
3. `google_drive_write_file(file_content="internal://...", file_name="transcript.txt")`
4. `google_drive_write_file(file_content="<analysis>", file_name="analysis.txt")` (tools can accept either plain text or an opaque reference)

## Internal tools

Internal tools operate on data referenced by an `internal://...` opaque ID so agents can inspect or extract portions of large values without exposing the full payload. These are useful when prompts must enforce partial reads (slice, grep, line reads) while forbidding full reads.

| Tool | Arguments | Description                                                                                                                                         |
|------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `internal_resource_read` | `opaque_reference` | Resolve an opaque reference and return the full value. Use as a last resort, after trying slicing, when the agent needs the full value. |
| `internal_resource_read_slice` | `opaque_reference`, `start_index`, `length` | Return a substring slice; supports negative `start_index` (Python-style) to count from the end.                                                     |
| `internal_resource_length` | `opaque_reference` | Return the length of the resolved value.                                                                                                            |
| `internal_resource_read_lines` | `opaque_reference`, `start_line`, `line_count` | Return a range of lines (zero-based `start_line`, negative counts from end).                                                                        |
| `internal_resource_grep` | `opaque_reference`, `pattern`, `window` | Regex search with context lines before/after each match.                                                                                            |

## Test results

<style>
.foo table {
    width: 50%;
    border-collapse: collapse;
}
.foo table th:first-of-type {
    width: 30%;
}
.foo table th:nth-of-type(2) {
    width: 10%;
}
.foo table th:nth-of-type(3) {
    width: 10%;
}
.foo table th:nth-of-type(4) {
    width: 20%;
}
</style>

I experimented with a few models to verify the concept. I tried both strong and older/weaker models, to see how well they follow the opaque reference handling instructions. I tested with a few additional few-shot examples (default CLI argument) and zero-shot prompts.

I tested Tool Context Relay with following models

### OpenAI GPT models



<div class="foo">

| Model       | Prompt Id | Few-shot | Validation |
|-------------|-----------|----------|------------|
| gpt-4o-mini | case0     | -        | ✅          |
| gpt-4o-mini | case1     | -        | ✅          |
| gpt-4o-mini | case2     | -        | ❌          |
| gpt-4o-mini | case3     | -        | ❌          |
| gpt-4o-mini | case4     | -        | ✅          |
| gpt-4o-mini | web1      | -        | ✅          |
| gpt-4o-mini | case0     | ✔        | ✅          |
| gpt-4o-mini | case1     | ✔        | ✅          |
| gpt-4o-mini | case2     | ✔        | ✅          |
| gpt-4o-mini | case3     | ✔        | ❌          |
| gpt-4o-mini | case4     | ✔        | ✅          |
| gpt-4o-mini | web1      | ✔        | ✅          |

| Model       | Prompt Id | Few-shot | Validation |
|-------------|-----------|----------|---------------|
| gpt-4o      | case0     | -        | ✅             |
| gpt-4o      | case1     | -        | ✅             |
| gpt-4o      | case2     | -        | ✅             |
| gpt-4o      | case3     | -        | ✅             |
| gpt-4o      | case4     | -        | ✅             |
| gpt-4o      | web1      | -        | ✅             |
| gpt-4o      | case0     | ✔        | ✅             |
| gpt-4o      | case1     | ✔        | ✅             |
| gpt-4o      | case2     | ✔        | ✅             |
| gpt-4o      | case3     | ✔        | ✅             |
| gpt-4o      | case4     | ✔        | ✅             |
| gpt-4o      | web1      | ✔        | ✅             |
 

| Model      | Prompt Id | Few-shot | Validation |
|------------|-----------|----------|------------|
| gpt-5-mini | case0     | -        | ✅          |
| gpt-5-mini | case1     | -        | ✅          |
| gpt-5-mini | case2     | -        | ✅          |
| gpt-5-mini | case3     | -        | ✅          |
| gpt-5-mini | case4     | -        | ✅          |
| gpt-5-mini | web1      | -        | ✅          |
| gpt-5-mini | case0     | ✔        | ✅          |
| gpt-5-mini | case1     | ✔        | ✅          |
| gpt-5-mini | case2     | ✔        | ✅          |
| gpt-5-mini | case3     | ✔        | ✅          |
| gpt-5-mini | case4     | ✔        | ✅          |
| gpt-5-mini | web1      | ✔        | ✅          |


| Model   | Prompt Id | Few-shot | Validation |
|---------|-----------|----------|------------|
| gpt-5.2 | case0     | -        | ✅          |
| gpt-5.2 | case1     | -        | ✅          |
| gpt-5.2 | case2     | -        | ✅          |
| gpt-5.2 | case3     | -        | ✅          |
| gpt-5.2 | case4     | -        | ✅          |
| gpt-5.2 | web1      | -        | ✅          |
| gpt-5.2 | case0     | ✔        | ✅          |
| gpt-5.2 | case1     | ✔        | ✅          |
| gpt-5.2 | case2     | ✔        | ✅          |
| gpt-5.2 | case3     | ✔        | ✅          |
| gpt-5.2 | case4     | ✔        | ✅          |
| gpt-5.2 | web1      | ✔        | ✅          |

### Qwen 3 model

#### Boxing method: opaque reference (default)

| Model                   | Prompt Id | Few-shot | Validation |
|-------------------------|-----------|----------|------------|
| Qwen/Qwen3-8B-GGUF:Q8_0 | case0     | -        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case1     | -        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case2     | -        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case3     | -        | ❌          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case4     | -        | ❌          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | web1      | -        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case0     | ✔        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case1     | ✔        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case2     | ✔        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case3     | ✔        | ✅          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | case4     | ✔        | ❌          |
| Qwen/Qwen3-8B-GGUF:Q8_0 | web1      | ✔        | ❌          |


| Model                    | Prompt Id | Few-shot | Validation |
|--------------------------|-----------|----------|------------|
| Qwen/Qwen3-14B:Q8_0      | case0     | -        | ✅          |
| Qwen/Qwen3-14B:Q8_0      | case1     | -        | ✅          |
| Qwen/Qwen3-14B:Q8_0      | case2     | -        | ❌          |
| Qwen/Qwen3-14B:Q8_0      | case3     | -        | ❌          |
| Qwen/Qwen3-14B:Q8_0      | case4     | -        | ❌          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | case0     | -        | ✅          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | case1     | -        | ✅          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | case2     | -        | ❌          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | case3     | -        | ✅          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | case4     | -        | ❌          |
| Qwen/Qwen3-14B-GGUF:Q8_0 | web1      | -        | ✅          |

#### Alternative boxing method: JSON

 | Model         | Prompt Id | Few-shot | Validation |
|---------------|-----------|----------|----------|
| qwen3-8B:Q8_0 | case0     | -        | ✅        |
| qwen3-8B:Q8_0 | case1     | -        | ❌        |
| qwen3-8B:Q8_0 | case2     | -        | ❌        |
| qwen3-8B:Q8_0 | case3     | -        | ✅        |
| qwen3-8B:Q8_0 | case4     | -        | ❌        |
| qwen3-8B:Q8_0 | case0     | ✔        | ✅        |
| qwen3-8B:Q8_0 | case1     | ✔        | ✅        |
| qwen3-8B:Q8_0 | case2     | ✔        | ✅        |
| qwen3-8B:Q8_0 | case3     | ✔        | ❌        |
| qwen3-8B:Q8_0 | case4     | ✔        | ✅        |

### Bielik v3 model


 | Model              | Prompt Id | Few-shot | Validation |
|--------------------|-----------|----------|-----------------|
| Bielik-11B-v3:Q8_0 | case0     | -        | ✅               |
| Bielik-11B-v3:Q8_0 | case1     | -        | ✅               |
| Bielik-11B-v3:Q8_0 | case2     | -        | ✅               |
| Bielik-11B-v3:Q8_0 | case3     | -        | ❌               |
| Bielik-11B-v3:Q8_0 | case4     | -        | ❌               |
| Bielik-11B-v3:Q8_0 | web1      | -        | ❌               |
| Bielik-11B-v3:Q8_0 | case0     | ✔        | ✅               |
| Bielik-11B-v3:Q8_0 | case1     | ✔        | ✅               |
| Bielik-11B-v3:Q8_0 | case2     | ✔        | ✅               |
| Bielik-11B-v3:Q8_0 | case3     | ✔        | ❌               |
| Bielik-11B-v3:Q8_0 | case4     | ✔        | ✅               |
| Bielik-11B-v3:Q8_0 | web1      | ✔        | ✅               |

### Deepseek

| Model                  | Prompt Id | Few-shot | Validation |
|------------------------|-----------|----------|------------|
| deepseek/deepseek-v3.2 | case0     | -        | ✅          |
| deepseek/deepseek-v3.2 | case1     | -        | ✅          |
| deepseek/deepseek-v3.2 | case2     | -        | ❌          |
| deepseek/deepseek-v3.2 | case3     | -        | ✅          |
| deepseek/deepseek-v3.2 | case4     | -        | ✅          |
| deepseek/deepseek-v3.2 | web1      | -        | ❌          |
| deepseek/deepseek-v3.2 | case0     | ✔        | ✅          |
| deepseek/deepseek-v3.2 | case1     | ✔        | ✅          |
| deepseek/deepseek-v3.2 | case2     | ✔        | ✅          |
| deepseek/deepseek-v3.2 | case3     | ✔        | ❌          |
| deepseek/deepseek-v3.2 | case4     | ✔        | ✅          |
| deepseek/deepseek-v3.2 | web1      | ✔        | ✅          |


</div>

## Conclusion (based on test results)

Based on the tables above (limited experiments):

- Flagship models like `gpt-4o` and `gpt-5.2` were reliable even without few-shot examples, so a strong “training-style” system prompt may not be strictly required for them in practice.
- Weaker/smaller models (especially `*-mini`, `qwen-3b` and few others) were noticeably less consistent without extra guidance; for these, few-shot examples improved reliability across all models, especially for the weaker ones.
- Overall, the Tool Context Relay pattern worked well across all tested models when few-shot examples were provided, demonstrating its effectiveness in managing long tool outputs without overwhelming the model's context. 
- Few-shot examples likely won’t be necessary for weaker models after fine-tuning on similar tasks, but that’s outside the scope of this PoC.

---

## Technical details

### Setup

Requires **Python 3.14+**.

### Environment configuration

- **Providers:** define one block per backend using uppercase prefixes (`OPENAI`, `OPENROUTER`, `LOCAL`). Each block can set `_API_KEY`/`_COMPAT_API_KEY`, `_MODEL`, `_BASE_URL`/`_BASEURL`/`_API_BASE`/`_ENDPOINT` (required for non-OpenAI providers), and `_BACKEND_PROVIDER`.
- **Profiles:** the CLI looks for `<PROFILE>_PROVIDER`, `<PROFILE>_MODEL`, `<PROFILE>_TEMPERATURE`, and `<PROFILE>_BACKEND_PROVIDER`. Profile names are case-insensitive (e.g., `deepseek` matches `DEEPSEEK_...`). Set `TOOL_CONTEXT_RELAY_PROFILE` or `--profile` to choose the active profile; the default is `openai`.
- **OpenRouter extras:** requests that target the `OPENROUTER` provider automatically add `provider.allow_fallbacks=false` and `provider.data_collection=deny`. Use `<PROFILE>_BACKEND_PROVIDER` to choose a downstream backend (e.g., `DEEPSEEK_BACKEND_PROVIDER=atlas-cloud/fp8`).

Simple `.env` example covering the three supported providers:

```sh
# provider definitions
OPENAI_API_KEY="sk-your-openai-key"
OPENAI_MODEL="gpt-4o"

OPENROUTER_API_KEY="sk-your-openrouter-key"
OPENROUTER_BASE_URL="https://openrouter.ai/v1"

LOCAL_BASE_URL="http://127.0.0.1:1234/v1"
LOCAL_MODEL="speaksleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"

# profile wiring
OPENAI_PROVIDER=openai
OPENAI_MODEL=gpt-4o

DEEPSEEK_PROVIDER=openrouter
DEEPSEEK_MODEL="deepseek/deepseek-v3.2"
DEEPSEEK_BACKEND_PROVIDER="atlas-cloud/fp8"

LOCAL_PROVIDER=local
LOCAL_MODEL="speaksleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"
LOCAL_TEMPERATURE=0.1
```

Put all of these vars in `.env` (loaded automatically via `python-dotenv`) and switch profiles with `TOOL_CONTEXT_RELAY_PROFILE=<name>` or `--profile <name>`. Additional providers and profiles just reuse the same naming conventions described above.

`.env.example` lists placeholders for the built-in profiles (`openai`, `deepseek`, `local`), so copy it before filling secrets.

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

### Run tests

- Unit tests + compile checks: `make ci`
- Integration tests (require API key + reachable endpoint): `make integration`

### Notes

`tool-context-relay` loads environment variables from a local `.env` file (if present) via `python-dotenv`.
