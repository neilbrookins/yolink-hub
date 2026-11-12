"""The YoLink Hub integration's icon, drawn at any size, for the brand images:

    python3 tools/draw_icon.py 256 custom_components/yolink_hub/brand/icon.png \
        512 custom_components/yolink_hub/brand/icon@2x.png

A dark tile with a hub and the words "YoLink HUB", so it isn't mistaken for
the official YoLink integration's logo. Coordinates are in 128-pixel units.
Needs a bold sans font: Liberation Sans Bold or DejaVu Sans Bold.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

TILE, WHITE, TEAL, HUB_EDGE = (30, 43, 56), (255, 255, 255), (47, 217, 184), (200, 214, 222)
FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

def font(px):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            pass
    raise SystemExit("No bold sans font found")

def centered(d, y, text, f, fill, width):
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text(((width - (r - l)) / 2 - l, y - t), text, font=f, fill=fill)

def icon(size):
    ss = 4                                   # supersampling
    k = size * ss / 128
    W = size * ss
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = lambda *v: [round(x * k) for x in v]
    d.rounded_rectangle(s(0, 0, 128, 128), radius=round(24 * k), fill=TILE)
    # radio waves above the hub
    for r, w in ((15, 4), (25, 4)):
        d.arc(s(64 - r, 34 - r, 64 + r, 34 + r), start=225, end=315,
              fill=TEAL, width=round(w * k))
    # the hub: a rounded box with three status lights
    d.rounded_rectangle(s(36, 34, 92, 52), radius=round(7 * k), fill=WHITE,
                        outline=HUB_EDGE, width=round(1.5 * k))
    for x in (54, 64, 74):
        d.ellipse(s(x - 2.6, 43 - 2.6, x + 2.6, 43 + 2.6), fill=TEAL)
    centered(d, 62 * k, "YoLink", font(round(25 * k)), WHITE, W)
    centered(d, 92 * k, "HUB", font(round(24 * k)), TEAL, W)
    return im.resize((size, size), Image.LANCZOS)

for size, path in zip(map(int, sys.argv[1::2]), sys.argv[2::2]):
    icon(size).save(path, optimize=True)
