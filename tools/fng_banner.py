"""Fear & Greed gauge banner (1280x580), Mr. Marketcap style.

Usage: python3 tools/fng_banner.py <value> <label> <yday_value> <yday_label> <week_value> <week_label> <out.jpg>
"""
import asyncio, html, math, os, sys, tempfile
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = "file://" + os.path.join(HERE, "fonts")


def tone(v):
    return "#EF5350" if v < 25 else "#F7931A" if v < 45 else "#FDD835" if v < 55 else "#7CCB6B" if v < 75 else "#26A69A"


def page(val, label, yv, yl, wv, wl):
    cx, cy, r = 300, 345, 190
    ang = math.radians(180 - val * 1.8)            # 180deg = 0, 0deg = 100
    mx, my = cx + r * math.cos(ang), cy - r * math.sin(ang)
    rot = 90 - (180 - val * 1.8)                    # triangle pointing to the centre
    col = tone(val)
    row = lambda top, name, v, l: f"""<div class="row" style="top:{top}px"><div><div class="k">{name}</div><div class="l">{html.escape(l)}</div></div><div class="v">{v}</div></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: I; src: url('{FONTS}/Inter-Regular.otf'); font-weight:400; }}
@font-face {{ font-family: I; src: url('{FONTS}/Inter-SemiBold.otf'); font-weight:700; }}
@font-face {{ font-family: V; src: url('{FONTS}/Vazirmatn-Bold.ttf'); font-weight:700; }}
html,body {{ margin:0; background:#0E0E10; }}
#b {{ position:relative; width:1280px; height:580px; overflow:hidden; font-family:I,sans-serif; color:#fff;
  background: radial-gradient(900px 520px at 28% 60%, {col}30, rgba(14,14,16,0) 70%), #0E0E10; }}
#grid {{ position:absolute; inset:0; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px); background-size:64px 64px; }}
#title {{ position:absolute; left:0; right:0; top:34px; text-align:center; font-family:V; font-weight:700; font-size:56px; direction:rtl; }}
#gauge {{ position:absolute; left:0; top:0; }}
#num {{ position:absolute; left:{cx-150}px; width:300px; top:{cy-118}px; text-align:center; font-weight:700; font-size:120px; line-height:1; letter-spacing:-3px; }}
#lab {{ position:absolute; left:{cx-190}px; width:380px; top:{cy+6}px; text-align:center; font-weight:700; font-size:42px; color:{col}; }}
.row {{ position:absolute; left:720px; width:440px; height:90px; display:flex; justify-content:space-between; align-items:center; }}
.k {{ font-size:28px; color:#9a9aa0; }} .l {{ font-size:34px; font-weight:700; margin-top:4px; }} .v {{ font-size:70px; font-weight:700; }}
.sep {{ position:absolute; left:720px; width:440px; top:315px; height:1px; background:#2a2a2e; }}
#bar {{ position:absolute; left:50%; bottom:112px; width:72px; height:5px; margin-left:-36px; background:#F7931A; border-radius:2px; }}
#src {{ position:absolute; left:40px; bottom:20px; font-size:20px; color:#6a6a70; }}
#sig {{ position:absolute; left:0; right:0; bottom:20px; text-align:center; }}
#sig .w {{ font-weight:700; font-size:36px; letter-spacing:12px; color:#f1f1f3; padding-left:12px; }}
#sig .h {{ font-size:22px; color:#9a9aa0; margin-top:6px; }}
</style></head><body><div id="b"><div id="grid"></div>
<div id="title">شاخص ترس و طمع</div>
<svg id="gauge" width="1280" height="580">
<defs><linearGradient id="g" x1="{cx-r}" y1="0" x2="{cx+r}" y2="0" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="#EF5350"/><stop offset="0.28" stop-color="#F7931A"/><stop offset="0.5" stop-color="#FDD835"/><stop offset="0.72" stop-color="#7CCB6B"/><stop offset="1" stop-color="#26A69A"/></linearGradient></defs>
<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" stroke="url(#g)" stroke-width="36" stroke-linecap="round"/>
<circle cx="{mx:.1f}" cy="{my:.1f}" r="17" fill="#f1f1f3" stroke="#0E0E10" stroke-width="5"/>
</svg>
<div id="num">{val}</div><div id="lab">{html.escape(label)}</div>
{row(185, "Yesterday", yv, yl)}<div class="sep"></div>{row(335, "Last Week", wv, wl)}
<div id="bar"></div>
<div id="sig"><div class="w">MR_MARKETCAP</div><div class="h">t.me/Mr_marketcap</div></div>
</div></body></html>"""


async def render(args, out):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "b.html")
        open(path, "w").write(page(int(args[0]), args[1], int(args[2]), args[3], int(args[4]), args[5]))
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 580}, device_scale_factor=1)
            await pg.goto("file://" + path)
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(300)
            if out.lower().endswith((".jpg", ".jpeg")):
                await pg.screenshot(path=out, type="jpeg", quality=80)
            else:
                await pg.screenshot(path=out)
            await b.close()


if __name__ == "__main__":
    if len(sys.argv) != 8:
        sys.exit(__doc__)
    asyncio.run(render(sys.argv[1:7], sys.argv[7]))
