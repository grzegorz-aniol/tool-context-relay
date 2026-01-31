.PHONY: ci integration


PROMPT_1 := "Generate transcript of YT video with video_id='123' and then pass it for deep analysis."
PROMPT_2 := "Generate transcript of YT video with video_id='123' and save it to a file at google drive named 'transcript.txt'."
PROMPT_3 := "Generate transcript of YT video with video_id='123' and then pass it for deep analysis. Then, let me know what number is included in the end of the transcript."
PROMPT_4 := "Generate transcript of YT video with video_id='123' and then pass it for deep analysis. Then, save both the transcript and the analysis to files at google drive named 'transcript.txt' and 'analysis.txt' respectively."

OPENAI_COMPAT_URL := "http://127.0.0.1:1234/v1"
OPENAI_COMPAT_MODEL := "speakleash/Bielik-11B-v3.0-Instruct-GGUF:Bielik-11B-v3.0-Instruct.Q8_0.gguf"

ci:
	uv run python -m compileall -q src tests
	uv run python -m pytest -q

integration:
	uv run python -m pytest -m integration -v tests/integration/

case1:
	tool-context-relay ${PROMPT_1}

case1-compat:
	tool-context-relay --provider openai-compat \
		--endpoint ${OPENAI_COMPAT_URL} \
		--model ${OPENAI_COMPAT_MODEL} \
		${PROMPT_1}

case2:
	tool-context-relay ${PROMPT_2}

case2-compat:
	tool-context-relay --provider openai-compat \
		--endpoint ${OPENAI_COMPAT_URL} \
		--model ${OPENAI_COMPAT_MODEL} \
		${PROMPT_2}

case3:
	tool-context-relay ${PROMPT_3}

case3-compat:
	tool-context-relay --provider openai-compat \
		--endpoint ${OPENAI_COMPAT_URL} \
		--model ${OPENAI_COMPAT_MODEL} \
		${PROMPT_3}

case4:
	tool-context-relay ${PROMPT_3}

case4-compat:
	tool-context-relay --provider openai-compat \
		--endpoint ${OPENAI_COMPAT_URL} \
		--model ${OPENAI_COMPAT_MODEL} \
		${PROMPT_3}