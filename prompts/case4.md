---
id: case4
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
  - tool_name: deep_check
    opaque_id_input: true
  - tool_name: google_drive_write_file
    opaque_id_input: true
  - tool_name: google_drive_write_file
expect_internal_resolve: false
---
Generate a transcript of the YouTube video with video_id='123' and then pass it to Deep Check for analysis.
Then save both the transcript and the analysis to files on Google Drive named 'transcript.txt' and 'analysis.txt', respectively.
