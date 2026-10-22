"""Telegram HTML helper: first line bold, rest escaped plain text.
Every non-empty line (except hashtag and @channel lines) starts with an invisible RLM so lines that begin with
Latin text (tickers, @handle, hashtags) stay right-aligned."""
import html

RLM = "‏"


def rtl(text):
    def ok(l):
        t = l.strip()
        return bool(t) and not l.startswith(RLM) and not t.startswith(("#", "@"))   # hashtags / channel link exempt
    return "\n".join((RLM + l) if ok(l) else l for l in text.split("\n"))


def bold_first(text, rtl_mark=True):
    first, _, rest = (rtl(text) if rtl_mark else text).partition("\n")
    return f"<b>{html.escape(first, quote=False)}</b>" + (("\n" + html.escape(rest, quote=False)) if rest else "")
