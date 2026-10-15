import html


def esc(value) -> str:
    """Escapes user-controlled text for Telegram parse_mode=HTML (None -> empty string)."""
    return "" if value is None else html.escape(str(value), quote=False)
