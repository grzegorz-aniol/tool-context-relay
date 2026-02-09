from tool_context_relay.agent.pretty import emit_default


def fun_send_email(to: str, body: str) -> str:
    """Simulate sending an email.

    Args:
        to (str): The recipient email address.
        body (str): The email body to send.
    Returns:
        str: A confirmation message.
    """
    emit_default(
        f"Simulated email send. to={to!r}, body_length={len(body)}",
        group=fun_send_email.__name__,
    )
    preview = body[:60].replace("\n", " ")
    return f"Email sent to {to!r}. Body length={len(body)}. Preview='{preview}'"
