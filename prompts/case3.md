---
id: case3
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
  - tool_name: deep_check
    opaque_id_input: true
  - tool_name: internal_resource_read_slice
    opaque_id_input: true
forbidden_tools:
  - google_drive_write_file
  - internal_resource_read
---
Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.
Then let me know what number appears at the end of the transcript.
