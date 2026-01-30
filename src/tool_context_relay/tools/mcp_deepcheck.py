from tool_context_relay.agent.pretty import emit_default


# This function simulates a deep check analysis on the provided text.
# It logs input text characteristics (len, prefix) to be sure the text is received correctly,
def fun_deep_check(text: str) -> str:
    """
    Perform deep analysis of a provided text.

    Args:
        text (str): The text to be checked.
    Returns:
        str: A summary of the analysis.
    """
    emit_default(
        f"Performing deep check on the provided text. Length: {len(text)}, Starting: '{text[:30]}...'",
        group=fun_deep_check.__name__,
    )
    result = f"Analyzed text {len(text)} characters long. No issues found. Beginning: ##{text[:50]}...##"
    emit_default(f"Deep check completed. Emitting result of length {len(result)}.", group=fun_deep_check.__name__)
    return result
