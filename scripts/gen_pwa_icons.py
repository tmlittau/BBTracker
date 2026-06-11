#!/usr/bin/env python3
"""Generate BBTracker PWA icons (a white dumbbell on an indigo field).

Writes PNGs into frontend/static/ for the web manifest + Apple home screen.
Run:  backend/.venv/bin/python scripts/gen_pwa_icons.py
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")
BG = (79, 70, 229)  # indigo-600
FG = (255, 255, 255)


def draw_dumbbell(size: int, glyph_scale: float) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    c = size / 2
    half = size * glyph_scale / 2  # half the glyph's horizontal extent
    plate_w = size * glyph_scale * 0.14
    inner_h = size * glyph_scale * 0.50
    outer_h = size * glyph_scale * 0.74
    bar_h = size * glyph_scale * 0.13

    def vbar(cx: float, h: float, w: float) -> None:
        d.rounded_rectangle(
            [cx - w / 2, c - h / 2, cx + w / 2, c + h / 2], radius=w * 0.4, fill=FG
        )

    # Handle joining the inner plates.
    d.rounded_rectangle(
        [c - half * 0.62, c - bar_h / 2, c + half * 0.62, c + bar_h / 2],
        radius=bar_h / 2, fill=FG,
    )
    # Plates: inner (shorter) + outer (taller) on each side.
    vbar(c - half * 0.62, inner_h, plate_w)
    vbar(c - half * 0.92, outer_h, plate_w)
    vbar(c + half * 0.62, inner_h, plate_w)
    vbar(c + half * 0.92, outer_h, plate_w)
    return img


ICONS = [
    ("icon-192.png", 192, 0.70),
    ("icon-512.png", 512, 0.70),
    ("apple-touch-icon.png", 180, 0.70),
    ("icon-maskable-512.png", 512, 0.56),  # smaller glyph for the maskable safe zone
]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, size, scale in ICONS:
        draw_dumbbell(size, scale).save(os.path.join(OUT, name))
        print("wrote", os.path.normpath(os.path.join(OUT, name)))

    # Multi-resolution favicon.ico (legacy browser tabs / bookmarks) from the same
    # glyph; drawn large and downsampled to the standard 16/32/48 px sizes.
    favicon = os.path.join(OUT, "favicon.ico")
    draw_dumbbell(256, 0.70).save(favicon, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote", os.path.normpath(favicon))
