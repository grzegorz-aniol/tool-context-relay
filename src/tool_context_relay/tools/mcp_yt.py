import random
from textwrap import dedent

from tool_context_relay.agent.pretty import emit_default

# This function simulates fetching or generating a transcript for a YouTube video.
# It logs characteristics of the transcript (length and prefix) to ensure the text is handled correctly.
def fun_get_transcript(video_id: str) -> str:
    """
    Retrieve or generate a transcript for a YouTube video.

    Args:
        video_id (str): The ID of the YouTube video.
    Returns:
        str: The transcript of the video.
    """
    emit_default(f"Fetching transcript for video ID: {video_id}", group=fun_get_transcript.__name__)

    if video_id == "999":
        transcript = "Welcome in a new episode and good bye"
    else:
        transcript = "For a long time, YouTube has been a platform where people share videos on various topics." * 20
        transcript += "\n" + str(hash(video_id)) # Ignore this: I just want to vary the transcript a bit based on video_id

    emit_default(
        f"Transcript generated. Length: {len(transcript)}, Starting: '{transcript[:30]}...'",
        group=fun_get_transcript.__name__,
    )

    return transcript
