.PHONY: ci

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

case1:
	tool-context-relay "Generate transcript of YT video with video_id='123' and then pass it for deep analysis."

case2:
	tool-context-relay \
		" \
		Generate transcript of YT video with video_id='123' and then pass it for deep analysis.\
		Then, let me know what number is included in the end of the transcript \
		"
