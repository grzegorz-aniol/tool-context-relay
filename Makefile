.PHONY: ci

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q
