---
id: case3
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
  - tool_name: deep_check
    opaque_id_input: true
forbidden_tools:
  - google_drive_write_file
expect_internal_resolve: true
---
Generate transcript of YT video with video_id='123' and then pass it to deep check analysis.
Then, let me know what number is included in the end of the transcript.
