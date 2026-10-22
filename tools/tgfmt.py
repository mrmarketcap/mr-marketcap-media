"""Telegram HTML helper: first line bold, rest escaped plain text.
Alignment rule (from the user): a line that contains any Persian letter is right-aligned
(invisible RLM at its start); a line with no Persian letters is left-aligned (invisible LRM)."""
import html, re

RLM = "‏"
LRM = "‎"
_FA = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def rtl(text):
    out = []
    for l in text.split("\n"):
        l = l.lstrip(RLM + LRM)
        if not l.strip():
            out.append(l)
        else:
            out.append((RLM if _FA.search(l) else LRM) + l)
    return "\n".join(out)


def bold_first(text, rtl_mark=True):
    first, _, rest = (rtl(text) if rtl_mark else text).partition("\n")
    return f"<b>{html.escape(first, quote=False)}</b>" + (("\n" + html.escape(rest, quote=False)) if rest else "")
