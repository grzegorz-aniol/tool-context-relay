---
id: case2
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
  - tool_name: google_drive_write_file
    opaque_id_input: true
forbidden_tools:
  - deep_check
expect_internal_resolve: false
---
Generate transcript of YT video with video_id='123' and save it to a file at google drive named 'transcript.txt'.
