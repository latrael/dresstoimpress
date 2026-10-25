"""Render the Niche "Arch" app icon (option A) with Pillow: full icon + adaptive-icon foreground.

    python app/assets/icon/make_icon.py      # writes icon-1024.png and icon-fg.png next to this file
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 4  # supersample, then downscale for smooth edges
MERLOT, CREAM, HOOK = (0x5B, 0x1F, 0x33), (0xFB, 0xF3, 0xEE), (0xE9, 0xB9, 0xA8)
HERE = Path(__file__).parent


def draw_arch(d: ImageDraw.ImageDraw, unit: float, ox: float, oy: float) -> None:
    """96-unit box: path M30 70 V44 a18 18 0 0 1 36 0 v26 (stroke 9, round caps) + hook dot at (66,26) r5."""
    w = 9 * unit
    r = w / 2

    def p(x, y):
        return (ox + x * unit, oy + y * unit)

    for x in (30, 66):  # legs with round feet
        d.line([p(x, 44), p(x, 70)], fill=CREAM, width=round(w))
        cx, cy = p(x, 70)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CREAM)
    c, R = p(48, 44), 18 * unit  # top half ring
    d.arc([c[0] - R - r, c[1] - R - r, c[0] + R + r, c[1] + R + r], 180, 360, fill=CREAM, width=round(w))
    hx, hy = p(66, 26)
    hr = 5 * unit
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=HOOK)


def render(size: int, bg, box: float) -> Image.Image:
    big = size * S
    im = Image.new("RGBA", (big, big), bg)
    unit = big / box
    pad = (box - 96) / 2 * unit
    draw_arch(ImageDraw.Draw(im), unit, pad, pad)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    render(1024, MERLOT + (255,), 96).convert("RGB").save(HERE / "icon-1024.png")
    render(1024, (0, 0, 0, 0), 144).save(HERE / "icon-fg.png")  # inside the adaptive 66% safe zone
    print("wrote", HERE / "icon-1024.png", HERE / "icon-fg.png")
