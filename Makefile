.PHONY: ci integration

#OPENAI_MODEL ?= gpt-4o
OPENAI_MODEL ?= gpt-5.2
#BIELIK_MODEL ?= speakleash_Bielik-11B-v3.0-Instruct-GGUF_Bielik-11B-v3.0-Instruct.f16.gguf
BIELIK_MODEL ?= speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

integration:
	uv run python -m pytest -m integration -v tests/integration/

# ------------- QWEN3 8b --------------

test-qwen-oneshot:
	uv run tool-context-relay \
		--profile qwen \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-qwen-fewshots:
	uv run tool-context-relay \
		--profile qwen \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"

test-json-qwen-oneshot:
	uv run tool-context-relay \
		--boxing json \
		--profile qwen \
		--show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-json-qwen-fewshots:
	uv run tool-context-relay \
		--boxing json \
		--profile qwen \
		--show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"

# ------------- QWEN3 14b --------------
test-qwen-14b-oneshot:
	uv run tool-context-relay \
		--profile qwen14b \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-qwen-14b-fewshots:
	uv run tool-context-relay \
		--profile qwen14b \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"

# ------------- BIELIK --------------

test-bielik-oneshot:
	 uv run tool-context-relay \
		--profile bielik \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-bielik-fewshots:
	 uv run tool-context-relay \
		--profile bielik \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"


# ------------- DeepSeek --------------
test-deepseek-oneshot:
	 uv run tool-context-relay \
		--profile deepseek \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-deepseek-fewshots:
	 uv run tool-context-relay \
		--profile deepseek \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"

# ------------- OPENAI --------------

test-openai-fewshots:
	 uv run tool-context-relay \
		--profile openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompts/*.md"

test-openai-oneshot:
	 uv run tool-context-relay \
		--profile openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"
