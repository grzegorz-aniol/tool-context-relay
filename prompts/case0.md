---
id: case0
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: false
  - tool_name: deep_check
    opaque_id_input: false
forbidden_tools:
  - google_drive_write_file
expect_internal_resolve: false
---
Generate a transcript of the YouTube video with video_id='999' and then pass it to Deep Check for analysis.
