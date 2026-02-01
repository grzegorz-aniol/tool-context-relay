.PHONY: ci integration

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

integration:
	uv run python -m pytest -m integration -v tests/integration/
