"""Neon scenes of the escape game: a sealed door, its lock and the code slots."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import font, png_bytes
from .cards import _neon_layer

W, H = 680, 340
COLORS = [neon.ORANGE, neon.CYAN, neon.RED]
ICONS = ["candle", "book", "skull"]


@lru_cache(maxsize=16)
def room_png(index: int, title: str, code_len: int, opened: bool = False, players: int = 1) -> bytes:
    color = COLORS[index % 3]
    img = neon.wall(W, H, index + 2).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 150)))
    img.alpha_composite(_neon_layer((W, H), title.upper(), (W // 2, 34), neon.fit_text(title.upper(), 30, 600),
                                    tuple(color), "mm"))
    # the door: an arch
    door = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(door)
    x0, x1, top, bottom = 250, 430, 70, 300
    d.arc((x0, top, x1, top + (x1 - x0)), 180, 360, fill=255, width=4)
    mid = top + (x1 - x0) // 2
    d.line((x0, mid, x0, bottom), fill=255, width=4)
    d.line((x1, mid, x1, bottom), fill=255, width=4)
    d.line((x0 - 20, bottom, x1 + 20, bottom), fill=255, width=4)
    if opened:
        d.polygon([(x0 + 4, mid), (x0 + 60, mid + 20), (x0 + 60, bottom - 10), (x0 + 4, bottom)], outline=255)
    img.alpha_composite(neon.glow(door, neon.PURPLE if not opened else neon.GREEN, 5))
    lock = neon.icon_light("lock" if not opened else "key", 70, neon.YELLOW if not opened else neon.GREEN)
    img.alpha_composite(lock, ((x0 + x1) // 2 - lock.width // 2, 150 - lock.height // 2))
    # code slots
    slot, gap = 34, 8
    total = code_len * slot + (code_len - 1) * gap
    sx = (W - total) // 2
    for k in range(code_len):
        box = (sx + k * (slot + gap), 222, sx + k * (slot + gap) + slot, 222 + slot + 6)
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(box, 6, outline=255, width=2)
        img.alpha_composite(neon.glow(m, color, 3))
        if opened:
            ImageDraw.Draw(img).text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "✓", font=font("body", 20, "Bold"),
                                     fill=(150, 255, 170), anchor="mm")
    # side decorations and progress
    for side, x in ((0, 110), (1, W - 110)):
        icon = neon.icon_light(ICONS[index % 3], 80, color)
        img.alpha_composite(icon, (x - icon.width // 2, 170 - icon.height // 2))
    for k in range(3):
        cx = W // 2 - 40 + k * 40
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((cx - 8, 310 - 8, cx + 8, 310 + 8), fill=255 if k < index or (k == index and opened) else 0,
                                  outline=255, width=2)
        img.alpha_composite(neon.glow(m, neon.GREEN if (k < index or (k == index and opened)) else (110, 100, 130), 3))
    label = f"{players} JOUEUR{'S' if players > 1 else ''}"
    img.alpha_composite(_neon_layer((W, H), label, (W - 80, H - 22), 14, (190, 180, 220), "mm"))
    return png_bytes(img.convert("RGB"))
