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

test-qwen-fewshots:
	uv run tool-context-relay \
		--profile qwen \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-qwen-oneshot:
	uv run tool-context-relay \
		--profile qwen \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

test-json-qwen-oneshot:
	uv run tool-context-relay \
		--boxing json \
		--profile qwen \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

test-json-qwen-fewshots:
	uv run tool-context-relay \
		--boxing json \
		--profile qwen \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-bielik-fewshots:
	 uv run tool-context-relay \
		--profile bielik \
		--model $(BIELIK_MODEL) \
		--temperature 0.1 \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-bielik-oneshot:
	 uv run tool-context-relay \
		--profile bielik \
		--model $(BIELIK_MODEL) \
		--temperature 0.1 \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

test-openai-fewshots:
	 uv run tool-context-relay \
		--profile openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-openai-oneshot:
	 uv run tool-context-relay \
		--profile openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"
