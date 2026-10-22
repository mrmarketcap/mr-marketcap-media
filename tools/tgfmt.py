"""Telegram HTML helper: first line bold, rest escaped plain text.
Every non-empty line starts with an invisible RLM so lines that begin with
Latin text (tickers, @handle, hashtags) stay right-aligned."""
import html

RLM = "‏"


def rtl(text):
    return "\n".join((RLM + l) if l.strip() and not l.startswith(RLM) else l for l in text.split("\n"))


def bold_first(text):
    first, _, rest = rtl(text).partition("\n")
    return f"<b>{html.escape(first, quote=False)}</b>" + (("\n" + html.escape(rest, quote=False)) if rest else "")
