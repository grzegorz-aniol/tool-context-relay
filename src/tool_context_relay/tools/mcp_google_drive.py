import uuid

from tool_context_relay.agent.pretty import emit_default


def fun_write_file_to_google_drive(file_content: str, file_name: str) -> str:
    """
    Write a file to Google Drive.

    Args:
        file_content (str): The content of the file to write.
        file_name (str): The name of the file in Google Drive.
    Returns:
        str: The generated file ID.
    """
    file_id = uuid.uuid4().hex
    emit_default(
        f"Simulated Google Drive write. file_name={file_name!r}, content_length={len(file_content)}, file_id={file_id}",
        group=fun_write_file_to_google_drive.__name__,
    )
    return file_id
