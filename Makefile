.PHONY: ci integration

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

integration:
	uv run python -m pytest -m integration -v tests/integration/

test-qwen:
	uv run tool-context-relay \
		--provider openai-compat \
		--endpoint http://127.0.0.1:1234/v1 \
		--model Qwen/Qwen3-8B-GGUF:Q8_0 \
		--no-show-system-instruction \
		--glob "prompt_cases/*.md"

test-openai:
	uv run python -m pytest -m integration -v -s --provider openai --model gpt-4o-mini
