"""Telegram HTML helper: first line bold, rest escaped plain text."""
import html


def bold_first(text):
    first, _, rest = text.partition("\n")
    return f"<b>{html.escape(first, quote=False)}</b>" + (("\n" + html.escape(rest, quote=False)) if rest else "")
