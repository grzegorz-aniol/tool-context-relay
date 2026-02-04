.PHONY: ci integration

OPENAI_MODEL ?= gpt-4o
#BIELIK_MODEL ?= speakleash_Bielik-11B-v3.0-Instruct-GGUF_Bielik-11B-v3.0-Instruct.f16.gguf
BIELIK_MODEL ?= speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

integration:
	uv run python -m pytest -m integration -v tests/integration/

test-qwen-fewshots:
	uv run tool-context-relay \
		--provider openai-compat \
		--endpoint http://127.0.0.1:1234/v1 \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-qwen-oneshot:
	uv run tool-context-relay \
		--provider openai-compat \
		--endpoint http://127.0.0.1:1234/v1 \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

test-bielik-fewshots:
	uv run tool-context-relay \
		--provider openai-compat \
		--endpoint http://127.0.0.1:1234/v1 \
		--model $(BIELIK_MODEL) \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-bielik-oneshot:
	uv run tool-context-relay \
		--provider openai-compat \
		--endpoint http://127.0.0.1:1234/v1 \
		--model $(BIELIK_MODEL) \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

test-openai-fewshots:
	uv run tool-context-relay \
		--provider openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--fewshots \
		--glob "prompt_cases/*.md"

test-openai-oneshot:
	uv run tool-context-relay \
		--provider openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompt_cases/*.md"

