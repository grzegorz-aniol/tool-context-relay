from tool_context_relay.agent.pretty import emit_default

IMAGE_URL_CAT = "https://demo.local/images/cat.png"
IMAGE_URL_DESK = "https://demo.local/images/desk.jpg"
IMAGE_URL_MOUNTAIN = "https://demo.local/images/mountain.webp"


def fun_get_img_description(img_url: str) -> str:
    """Return a concise description for a simulated image URL.

    Args:
        img_url (str): The image URL to describe.
    Returns:
        str: A short, two-sentence description.
    """
    if img_url == IMAGE_URL_CAT:
        description = "A small tabby cat sits on a windowsill. Soft daylight highlights its whiskers."
    elif img_url == IMAGE_URL_DESK:
        description = "A tidy desk holds a laptop, notebook, and pen. The scene feels calm and organized."
    elif img_url == IMAGE_URL_MOUNTAIN:
        description = "Snowy peaks rise above a dense pine forest. Low clouds drift across the ridge."
    else:
        description = "No recognizable image content appears in this URL. The simulated model found no labels."

    emit_default(
        f"Simulated image description. img_url={img_url!r}, length={len(description)}",
        group=fun_get_img_description.__name__,
    )
    return description
