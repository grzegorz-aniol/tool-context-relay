from tool_context_relay.agent.pretty import emit_default

_SCREENSHOT_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABgUlEQVQ4T6WTv0sD"
    "URCGv7c3Q6nQqKpVJQpVJp0k1nXo0E4s9VQyGZ3Nw8fK1q7mD0M0Qz6k3p8l9Z8d4"
    "ZkT4q0mG5j2uE4X5V7z7wH7nT8B7rQq6xkZtV5Jc2fQ6q9Hk3bQe2cQn2j7R1gA3d"
    "c1a0b8eQv5u9r7m7P7o7p1fR7XnqgK2Lw3Cz2a1a1q5o0Qv4n8P6mQfJmZbL5v5bH"
    "eKkqg8m7vZ8m2lOq4m0n4lW2uN8x6v9gqj0JrZQwH1rVJ5sQ7GQK5sZ2sQqH9q6iQ"
    "k6mQ4e7bD9f3tS7k8QAAAABJRU5ErkJggg=="
)


def fun_get_web_screenshot() -> str:
    """Return a simulated base64-encoded web screenshot.

    Returns:
        str: The base64-encoded image data.
    """
    emit_default(
        f"Simulated web screenshot. length={len(_SCREENSHOT_BASE64)}",
        group=fun_get_web_screenshot.__name__,
    )
    return _SCREENSHOT_BASE64
