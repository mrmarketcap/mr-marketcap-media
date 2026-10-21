"""Dollar (IRR) banner for @Mr_marketcap, 1280x700: big USD price plus gold and coin rows. Persian labels (Vazirmatn).

Usage: python3 tools/irr_banner.py '<json>' <out.jpg>
json = {"big": "269,600", "sub": "تومان · +0.2% نسبت به دیروز", "tone": "up|down|flat",
        "rows": [{"label": "طلای ۱۸ عیار (گرم)", "value": "27,148,000", "ch": 0.3}, ...]}   # ch may be null
"""
import asyncio, html, json, os, re, sys, tempfile
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = "file://" + os.path.join(HERE, "fonts")
COL = {"up": ("#26A69A", "rgba(38,166,154,0.22)"), "down": ("#EF5350", "rgba(239,83,80,0.22)"),
       "flat": ("#F7931A", "rgba(247,147,26,0.18)")}
LTR = "<span style='direction:ltr;unicode-bidi:isolate;display:inline-block;font-family:I'>{}</span>"


def ltr_numbers(text):
    return re.sub(r"([+-]?[0-9.]+%?)", lambda m: LTR.format(m.group(1)), html.escape(text))


def row_html(r):
    ch = r.get("ch")
    if ch is None or abs(ch) < 0.05:
        c, t = "#9a9aa0", "0.0%"
    else:
        c, t = ("#26A69A" if ch > 0 else "#EF5350"), f"{ch:+.1f}%"
    return (f"<div class='row'><div class='lab'>{html.escape(r['label'])}</div>"
            f"<div class='val'>{LTR.format(html.escape(r['value']))}</div>"
            f"<div class='chg' style='color:{c}'>{LTR.format(t)}</div></div>")


def page(d):
    col, glow = COL[d["tone"]]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: I; src: url('{FONTS}/Inter-Regular.otf'); font-weight:400; }}
@font-face {{ font-family: I; src: url('{FONTS}/Inter-SemiBold.otf'); font-weight:700; }}
@font-face {{ font-family: V; src: url('{FONTS}/Vazirmatn-Bold.ttf'); font-weight:700; }}
html,body {{ margin:0; background:#0E0E10; }}
#b {{ position:relative; width:1280px; height:700px; overflow:hidden; font-family:I,sans-serif; color:#fff;
  background: radial-gradient(900px 480px at 50% 34%, {glow}, rgba(14,14,16,0) 70%), #0E0E10; }}
#grid {{ position:absolute; inset:0; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px); background-size:64px 64px; }}
#pill {{ position:absolute; left:50%; top:38px; transform:translateX(-50%); background:#1a1a1d; border:1px solid #2c2c31; border-radius:60px; padding:6px 56px 10px; font-family:V; direction:rtl; font-weight:700; font-size:50px; white-space:nowrap; }}
#big {{ position:absolute; left:0; right:0; top:140px; text-align:center; font-weight:700; font-size:170px; letter-spacing:-4px; line-height:1; color:{col}; }}
#sub {{ position:absolute; left:0; right:0; top:340px; text-align:center; font-family:V; direction:rtl; font-weight:700; font-size:40px; color:#d6d6da; }}
#rows {{ position:absolute; left:200px; right:200px; top:420px; }}
.row {{ display:flex; align-items:center; justify-content:space-between; direction:ltr; height:64px; border-top:1px solid #2c2c31; }}
.lab {{ order:3; font-family:V; direction:rtl; font-weight:700; font-size:34px; color:#d6d6da; width:330px; text-align:right; }}
.val {{ order:1; font-weight:700; font-size:40px; width:300px; text-align:left; }}
.chg {{ order:2; font-weight:700; font-size:30px; width:140px; text-align:center; }}
#sig {{ position:absolute; left:0; right:0; bottom:20px; text-align:center; }}
#sig .w {{ font-weight:700; font-size:40px; letter-spacing:12px; color:#f1f1f3; padding-left:12px; }}
#sig .h {{ font-size:24px; color:#9a9aa0; margin-top:6px; }}
</style></head><body><div id="b"><div id="grid"></div>
<div id="pill">دلار آزاد</div><div id="big">{html.escape(d["big"])}</div><div id="sub">{ltr_numbers(d["sub"])}</div>
<div id="rows">{"".join(row_html(r) for r in d["rows"])}</div>
<div id="sig"><div class="w">MR_MARKETCAP</div><div class="h">t.me/Mr_marketcap</div></div>
</div></body></html>"""


async def render(d, out):
    with tempfile.TemporaryDirectory() as t:
        path = os.path.join(t, "b.html")
        open(path, "w").write(page(d))
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 700}, device_scale_factor=1)
            await pg.goto("file://" + path)
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=out, type="jpeg", quality=88)
            await b.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(render(json.loads(sys.argv[1]), sys.argv[2]))
