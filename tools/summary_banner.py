"""Daily market summary banner (1280x700): top gainers/losers of the last 24h.

Usage: python3 tools/summary_banner.py '<json>' <out.jpg>
json = {"head": "BTC $85,000 +2.1% · ETH $2,500 +1.2%", "gain": [["SOL", 6.2], ...], "lose": [["ADA", -4.1], ...]}
"""
import asyncio, html, json, os, sys, tempfile
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = "file://" + os.path.join(HERE, "fonts")


def rows(items):
    out = []
    for t, p in items:
        c = "#26A69A" if p >= 0 else "#EF5350"
        out.append(f'<div class="r"><span class="t">{html.escape(t)}</span><span class="p" style="color:{c}">{p:+.1f}%</span></div>')
    return "".join(out)


def page(d):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: I; src: url('{FONTS}/Inter-Regular.otf'); font-weight:400; }}
@font-face {{ font-family: I; src: url('{FONTS}/Inter-SemiBold.otf'); font-weight:700; }}
@font-face {{ font-family: V; src: url('{FONTS}/Vazirmatn-Bold.ttf'); font-weight:700; }}
html,body {{ margin:0; background:#0E0E10; }}
#b {{ position:relative; width:1280px; height:700px; overflow:hidden; font-family:I,sans-serif; color:#fff; background:#0E0E10; }}
#grid {{ position:absolute; inset:0; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px); background-size:64px 64px; }}
#title {{ position:absolute; left:0; right:0; top:30px; text-align:center; font-family:V; font-weight:700; font-size:56px; direction:rtl; }}
#head {{ position:absolute; left:0; right:0; top:118px; text-align:center; font-size:28px; color:#b8b8be; }}
.col {{ position:absolute; top:182px; width:520px; }}
.h {{ font-size:24px; letter-spacing:5px; color:#9a9aa0; font-weight:700; padding:0 8px 10px; border-bottom:1px solid #2a2a2e; }}
.r {{ display:flex; justify-content:space-between; align-items:center; height:62px; padding:0 8px; border-bottom:1px solid #1c1c20; font-size:38px; font-weight:700; }}
.p {{ font-size:38px; }}
#bar {{ position:absolute; left:50%; bottom:112px; width:72px; height:5px; margin-left:-36px; background:#F7931A; border-radius:2px; }}
#sig {{ position:absolute; left:0; right:0; bottom:20px; text-align:center; }}
#sig .w {{ font-weight:700; font-size:36px; letter-spacing:12px; color:#f1f1f3; padding-left:12px; }}
#sig .h2 {{ font-size:22px; color:#9a9aa0; margin-top:6px; }}
#src {{ position:absolute; left:40px; bottom:20px; font-size:20px; color:#6a6a70; }}
</style></head><body><div id="b"><div id="grid"></div>
<div id="title">{html.escape(d.get("title") or "خلاصهٔ بازار ۲۴ ساعت گذشته")}</div>
<div id="head">{html.escape(d["head"])}</div>
<div class="col" style="left:80px"><div class="h">TOP GAINERS</div>{rows(d["gain"])}</div>
<div class="col" style="left:680px"><div class="h">TOP LOSERS</div>{rows(d["lose"])}</div>
<div id="bar"></div><div id="src">Source: KuCoin</div>
<div id="sig"><div class="w">MR_MARKETCAP</div><div class="h2">t.me/Mr_marketcap</div></div>
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
