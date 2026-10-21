"""Dollar (IRR) banner, same look as stat_banner.py but pill and sub in Persian (Vazirmatn).

Generic Mr. Marketcap stat banner (same look as price_banner.py), 1280x580.

Usage: python3 tools/stat_banner.py <pill> <big> <sub> <up|down|flat> <output.jpg|png>
Example: python3 tools/stat_banner.py "FEAR & GREED" 63 "Greed · yesterday 55" up out.jpg
"""
import asyncio, html, re, os, sys, tempfile
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = "file://" + os.path.join(HERE, "fonts")
COL = {"up": ("#26A69A", "rgba(38,166,154,0.22)"), "down": ("#EF5350", "rgba(239,83,80,0.22)"),
       "flat": ("#F7931A", "rgba(247,147,26,0.18)")}


def page(pill, big, sub, tone):
    col, glow = COL[tone]
    size = 200 if len(big) <= 4 else 170
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: I; src: url('{FONTS}/Inter-Regular.otf'); font-weight:400; }}
@font-face {{ font-family: I; src: url('{FONTS}/Inter-SemiBold.otf'); font-weight:700; }}
@font-face {{ font-family: V; src: url('{FONTS}/Vazirmatn-Bold.ttf'); font-weight:700; }}
html,body {{ margin:0; background:#0E0E10; }}
#b {{ position:relative; width:1280px; height:580px; overflow:hidden; font-family:I,sans-serif; color:#fff;
  background: radial-gradient(900px 520px at 50% 52%, {glow}, rgba(14,14,16,0) 70%), #0E0E10; }}
#grid {{ position:absolute; inset:0; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px); background-size:64px 64px; }}
#pill {{ position:absolute; left:50%; top:46px; transform:translateX(-50%); background:#1a1a1d; border:1px solid #2c2c31; border-radius:60px; padding:6px 56px 10px; font-family:V; direction:rtl; font-weight:700; font-size:50px; white-space:nowrap; }}
#big {{ position:absolute; left:0; right:0; top:170px; text-align:center; font-weight:700; font-size:{size}px; letter-spacing:-4px; line-height:1; color:{col}; }}
#sub {{ position:absolute; left:0; right:0; top:378px; text-align:center; font-family:V; direction:rtl; font-weight:700; font-size:40px; color:#d6d6da; }}
#bar {{ position:absolute; left:50%; bottom:124px; width:72px; height:5px; margin-left:-36px; background:#F7931A; border-radius:2px; }}
#sig {{ position:absolute; left:0; right:0; bottom:24px; text-align:center; }}
#sig .w {{ font-weight:700; font-size:46px; letter-spacing:14px; color:#f1f1f3; padding-left:14px; }}
#sig .h {{ font-size:28px; color:#9a9aa0; margin-top:10px; }}
</style></head><body><div id="b"><div id="grid"></div>
<div id="pill">{html.escape(pill)}</div><div id="big">{html.escape(big)}</div><div id="sub">{re.sub(r"([+-]?[0-9.]+%?)", r"<span style='direction:ltr;unicode-bidi:isolate;display:inline-block;font-family:I'>\1</span>", html.escape(sub))}</div>
<div id="bar"></div>
<div id="sig"><div class="w">MR_MARKETCAP</div><div class="h">t.me/Mr_marketcap</div></div>
</div></body></html>"""


async def render(pill, big, sub, tone, out):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "b.html")
        open(path, "w").write(page(pill, big, sub, tone))
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 580}, device_scale_factor=1)
            await pg.goto("file://" + path)
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(300)
            if out.lower().endswith((".jpg", ".jpeg")):
                await pg.screenshot(path=out, type="jpeg", quality=88)
            else:
                await pg.screenshot(path=out)
            await b.close()


if __name__ == "__main__":
    if len(sys.argv) != 6 or sys.argv[4] not in COL:
        sys.exit(__doc__)
    asyncio.run(render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
