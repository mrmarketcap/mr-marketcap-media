"""Render a Mr. Marketcap price-alert banner (BTC or ETH round level).

Usage: python3 tools/price_banner.py <BTC|ETH> <level> <up|down> <output.png>
Example: python3 tools/price_banner.py ETH 2500 up eth-2500.png

Needs Playwright with Chromium (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers if
the browser is not found). Fonts (Inter) come from tools/fonts.
"""
import asyncio
import os
import sys
import tempfile

from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = "file://" + os.path.join(HERE, "fonts")

ETH_LOGO = '''<svg id="logo" viewBox="0 0 124 124"><circle cx="62" cy="62" r="60" fill="#2a2c3a" stroke="#4a4d63" stroke-width="3"/><g transform="translate(62 62)"><path d="M0 -38 L22 2 L0 -9 L-22 2 Z" fill="#c9cbe0"/><path d="M0 -9 L22 2 L0 14 L-22 2 Z" fill="#8f92b3"/><path d="M-22 10 L0 21 L0 38 Z" fill="#8f92b3"/><path d="M22 10 L0 21 L0 38 Z" fill="#c9cbe0"/></g></svg>'''
BTC_LOGO = '''<svg id="logo" viewBox="0 0 124 124"><circle cx="62" cy="62" r="60" fill="#F7931A"/><text x="62" y="86" text-anchor="middle" font-family="I" font-weight="700" font-size="76" fill="#ffffff">&#8383;</text></svg>'''


def banner(ticker, price, up):
    logo = ETH_LOGO if ticker == "ETH" else BTC_LOGO
    col = "#26A69A" if up else "#EF5350"
    glow = "rgba(38,166,154,0.22)" if up else "rgba(239,83,80,0.22)"
    arrow = ('<path d="M0 44 L36 0 L72 44 Z" fill="%s"/>' % col) if up else ('<path d="M0 0 L36 44 L72 0 Z" fill="%s"/>' % col)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: I; src: url('{FONTS}/Inter-Regular.otf'); font-weight:400; }}
@font-face {{ font-family: I; src: url('{FONTS}/Inter-SemiBold.otf'); font-weight:700; }}
html,body {{ margin:0; background:#0E0E10; }}
#b {{ position:relative; width:1280px; height:580px; overflow:hidden; font-family:I,sans-serif; color:#fff;
  background: radial-gradient(900px 520px at 50% 52%, {glow}, rgba(14,14,16,0) 70%), #0E0E10; }}
#grid {{ position:absolute; inset:0; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px); background-size:64px 64px; }}
#pill {{ position:absolute; left:50%; top:46px; transform:translateX(-50%); display:flex; align-items:center; gap:18px; background:#1a1a1d; border:1px solid #2c2c31; border-radius:60px; padding:14px 46px; font-weight:700; font-size:44px; letter-spacing:4px; }}
#price {{ position:absolute; left:0; right:0; top:178px; text-align:center; font-weight:700; font-size:180px; letter-spacing:-4px; line-height:1; }}
#arrow {{ position:absolute; left:50%; top:386px; transform:translateX(-50%); }}
#sig {{ position:absolute; left:0; right:0; bottom:24px; text-align:center; }}
#sig .w {{ font-weight:700; font-size:46px; letter-spacing:14px; color:#f1f1f3; padding-left:14px; }}
#sig .h {{ font-size:28px; color:#9a9aa0; margin-top:10px; }}
#logo {{ position:absolute; left:56px; top:30px; width:124px; height:124px; }}
#bar {{ position:absolute; left:50%; bottom:124px; width:72px; height:5px; margin-left:-36px; background:#F7931A; border-radius:2px; }}
</style></head><body><div id="b"><div id="grid"></div>
{logo}<div id="pill">{ticker}</div>
<div id="price">${price}</div>
<svg id="arrow" width="72" height="44" viewBox="0 0 72 44">{arrow}</svg>
<div id="bar"></div>
<div id="sig"><div class="w">MR_MARKETCAP</div><div class="h">t.me/Mr_marketcap</div></div>
</div></body></html>"""


async def render(ticker, level, up, out_png):
    html = banner(ticker, f"{level:,}", up)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "banner.html")
        with open(path, "w") as f:
            f.write(html)
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 580}, device_scale_factor=2)
            await pg.goto("file://" + path)
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(400)
            await pg.screenshot(path=out_png)
            await b.close()


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    t = sys.argv[1].upper()
    if t not in ("BTC", "ETH"):
        sys.exit("ticker must be BTC or ETH")
    lvl = int(sys.argv[2])
    d = sys.argv[3].lower()
    if d not in ("up", "down"):
        sys.exit("direction must be up or down")
    asyncio.run(render(t, lvl, d == "up", sys.argv[4]))
