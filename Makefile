.PHONY: ci integration \
	test-qwen-noshot test-qwen-fewshots test-json-qwen-noshot test-json-qwen-fewshots \
	test-qwen-14b-noshot test-qwen-14b-fewshots \
	test-bielik-noshot test-bielik-fewshots test-bielik-all \
	test-deepseek-noshot test-deepseek-fewshots \
	test-openai-noshot test-openai-fewshots \
	test-openai-gpt-4o-noshot test-openai-gpt-4o-fewshots \
	test-openai-gpt-4o-mini-noshot test-openai-gpt-4o-mini-fewshots \
	test-openai-gpt-5-mini-noshot test-openai-gpt-5-mini-fewshots \
	test-openai-gpt-5.2-noshot test-openai-gpt-5.2-fewshots \
	test-openai

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

test-qwen-noshot:
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

# ------------- QWEN3 14b --------------
test-qwen-14b-noshot:
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

test-bielik-noshot:
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

test-bielik-all: test-bielik-noshot test-bielik-fewshots

# ------------- DeepSeek --------------
test-deepseek-noshot:
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

test-openai-noshot:
	 uv run tool-context-relay \
		--profile openai \
		--model $(OPENAI_MODEL) \
		--no-show-system-instruction \
		--no-fewshots \
		--glob "prompts/*.md"

test-openai-gpt-4o-noshot:
	OPENAI_MODEL=gpt-4o $(MAKE) test-openai-noshot

test-openai-gpt-4o-fewshots:
	OPENAI_MODEL=gpt-4o $(MAKE) test-openai-fewshots

test-openai-gpt-4o-mini-noshot:
	OPENAI_MODEL=gpt-4o-mini $(MAKE) test-openai-noshot

test-openai-gpt-4o-mini-fewshots:
	OPENAI_MODEL=gpt-4o-mini $(MAKE) test-openai-fewshots

test-openai-gpt-5-mini-noshot:
	OPENAI_MODEL=gpt-5-mini $(MAKE) test-openai-noshot

test-openai-gpt-5-mini-fewshots:
	OPENAI_MODEL=gpt-5-mini $(MAKE) test-openai-fewshots

test-openai-gpt-5.2-noshot:
	OPENAI_MODEL=gpt-5.2 $(MAKE) test-openai-noshot

test-openai-gpt-5.2-fewshots:
	OPENAI_MODEL=gpt-5.2 $(MAKE) test-openai-fewshots

test-openai: \
	test-openai-gpt-4o-noshot test-openai-gpt-4o-fewshots \
	test-openai-gpt-4o-mini-noshot test-openai-gpt-4o-mini-fewshots \
	test-openai-gpt-5-mini-noshot test-openai-gpt-5-mini-fewshots \
	test-openai-gpt-5.2-noshot test-openai-gpt-5.2-fewshots
