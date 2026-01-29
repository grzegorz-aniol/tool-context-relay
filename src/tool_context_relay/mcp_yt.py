from textwrap import dedent

from tool_context_relay.pretty import emit_default


def fun_get_transcript(video_id: str) -> str:
    """
    Retrieve or generate a transcript for a YouTube video.

    Args:
        video_id (str): The ID of the YouTube video.
    Returns:
        str: The transcript of the video.
    """
    emit_default(f"Fetching transcript for video ID: {video_id}")
    transcript = """
    For a long time, YouTube has been a platform where people share videos on various topics.
    """ * 20
    transcript = dedent(transcript).strip()
    emit_default(f"Transcript generated. Length: {len(transcript)}, Starting: '{transcript[:30]}...'")
    return transcript
