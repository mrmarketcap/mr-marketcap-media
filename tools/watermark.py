"""Add the Mr. Marketcap watermark to a chart image.

Usage: python3 tools/watermark.py input.png output.png

Two quiet marks, in the spirit of a trading terminal's chart logo:
1. A light, letter-spaced "MR. MARKETCAP" wordmark with hairlines on each
   side, sitting faintly in the middle of the plot area (where the candles
   are, so it can't be cropped away without cutting the chart).
2. A small signature in the bottom-right corner: a thin orange bar, the
   wordmark, and the channel handle underneath.

Fonts (Inter, SIL Open Font License) live in tools/fonts so the result is
identical on every run.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

WORDMARK = "MR. MARKETCAP"
HANDLE = "t.me/Mr_marketcap"
ORANGE = (247, 147, 26)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def tracked_width(draw, text, fnt, tracking):
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    return sum(widths) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text, fnt, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def center_mark(layer, W, H):
    d = ImageDraw.Draw(layer)
    size = int(H * 0.052)
    fnt = font("InterDisplay-Light.otf", size)
    tracking = size * 0.32
    tw = tracked_width(d, WORDMARK, fnt, tracking)

    # middle of the plot area (left of the level labels, between header and x-axis)
    cx, cy = W * 0.43, H * 0.56
    x0 = cx - tw / 2
    top = d.textbbox((0, 0), "M", font=fnt)
    cap_h = top[3] - top[1]
    y0 = cy - cap_h / 2 - top[1]

    alpha = 28  # ~11% white: visible on the dark background, never in the way
    draw_tracked(d, (x0, y0), WORDMARK, fnt, (255, 255, 255, alpha), tracking)

    gap, line = size * 0.9, size * 2.2
    ly = cy
    lw = max(2, int(H * 0.0016))
    d.line([(x0 - gap - line, ly), (x0 - gap, ly)], fill=(255, 255, 255, alpha), width=lw)
    d.line([(x0 + tw + gap, ly), (x0 + tw + gap + line, ly)], fill=(255, 255, 255, alpha), width=lw)


def corner_signature(layer, W, H):
    d = ImageDraw.Draw(layer)
    s1 = int(H * 0.0155)
    s2 = int(H * 0.0135)
    f1 = font("Inter-SemiBold.otf", s1)
    f2 = font("Inter-Regular.otf", s2)
    t1 = s1 * 0.30
    t2 = s2 * 0.06

    w1 = tracked_width(d, WORDMARK, f1, t1)
    w2 = tracked_width(d, HANDLE, f2, t2)
    block_w = max(w1, w2)

    right = W - W * 0.036
    bottom = H - H * 0.038
    line_gap = s1 * 0.55
    b1 = d.textbbox((0, 0), "M", font=f1)
    b2 = d.textbbox((0, 0), "t", font=f2)
    h1 = b1[3] - b1[1]
    h2 = b2[3] - b2[1]
    block_h = h1 + line_gap + h2

    top = bottom - block_h
    x = right - block_w
    draw_tracked(d, (x, top - b1[1]), WORDMARK, f1, (255, 255, 255, 190), t1)
    draw_tracked(d, (x, top + h1 + line_gap - b2[1]), HANDLE, f2, (255, 255, 255, 110), t2)

    bar_w = max(2, int(H * 0.0028))
    bar_x = x - s1 * 0.85
    d.rectangle([bar_x, top, bar_x + bar_w, bottom], fill=ORANGE + (230,))


def main(src, dst):
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    center_mark(layer, W, H)
    corner_signature(layer, W, H)
    out = Image.alpha_composite(im, layer).convert("RGB")
    if dst.lower().endswith((".jpg", ".jpeg")):
        out.save(dst, quality=90)
    else:
        out.save(dst, optimize=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
