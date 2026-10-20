"""Add the @Mr_marketcap watermark to a chart image.

Usage: python3 tools/watermark.py input.png output.png
- a large faint diagonal mark across the middle (hard to crop out, data stays readable)
- a small orange handle in the bottom-right corner
"""
import glob, sys
from PIL import Image, ImageDraw, ImageFont

TEXT = "@Mr_marketcap"

def font(size):
    candidates = (
        glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)
        + glob.glob("/home/claude/rastikerdar/vazirmatn/fonts/ttf/Vazirmatn-Bold.ttf")
        + glob.glob("/usr/share/fonts/**/*Bold*.ttf", recursive=True)
    )
    if not candidates:
        sys.exit("no bold font found")
    return ImageFont.truetype(candidates[0], size)

def main(src, dst):
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    f = font(int(H * 0.12))
    bw = int(d.textlength(TEXT, font=f))
    big = Image.new("RGBA", (bw + 40, int(H * 0.18)), (0, 0, 0, 0))
    ImageDraw.Draw(big).text((20, 0), TEXT, font=f, fill=(255, 255, 255, 22))
    big = big.rotate(18, expand=True, resample=Image.BICUBIC)
    layer.alpha_composite(big, ((W - big.width) // 2, (H - big.height) // 2 + int(H * 0.025)))

    f2 = font(int(H * 0.022))
    tw = int(d.textlength(TEXT, font=f2))
    d.text((W - tw - int(W * 0.038), H - int(H * 0.046)), TEXT, font=f2, fill=(247, 147, 26, 170))

    out = Image.alpha_composite(im, layer)
    if dst.lower().endswith((".jpg", ".jpeg")):
        out.convert("RGB").save(dst, quality=90)
    else:
        out.convert("RGB").save(dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
