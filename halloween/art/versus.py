"""Animated « VS » intro for live challenges: two neon portraits slam in, lightning, VS."""
from __future__ import annotations

import math
import random
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageOps

from . import neon
from .cards import _gif_once, _neon_layer

W, H = 760, 300
AV = 128
LEFT_C, RIGHT_C = neon.CYAN, neon.PINK


def _portrait(data: bytes | None, color, fallback: str) -> Image.Image:
    """Round avatar inside a neon ring (or a neon monster when there is no avatar)."""
    size = AV + 48
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = 24
    img = None
    if data:
        try:
            img = ImageOps.fit(Image.open(BytesIO(data)).convert("RGBA"), (AV, AV), Image.LANCZOS)
        except Exception:  # noqa: BLE001 - a broken avatar must not break the challenge
            img = None
    disc = Image.new("L", (AV, AV), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, AV - 1, AV - 1), fill=255)
    if img is not None:
        img.putalpha(ImageChops.multiply(img.getchannel("A"), disc))
        out.alpha_composite(img, (pad, pad))
    else:
        bg = Image.new("RGBA", (AV, AV), (20, 10, 28, 255))
        bg.putalpha(disc)
        out.alpha_composite(bg, (pad, pad))
        icon = neon.icon_light(fallback, 90, color)
        out.alpha_composite(icon, ((size - icon.width) // 2, (size - icon.height) // 2))
    ring = Image.new("L", (size, size), 0)
    ImageDraw.Draw(ring).ellipse((pad - 4, pad - 4, pad + AV + 3, pad + AV + 3), outline=255, width=5)
    out.alpha_composite(neon.glow(ring, color, 6))
    return out


def _background():
    img = neon.wall(W, H, 2).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 140)))
    tint = Image.new("L", (W, H), 0)
    ImageDraw.Draw(tint).polygon([(0, 0), (W // 2 + 40, 0), (W // 2 - 40, H), (0, H)], fill=60)
    left = Image.new("RGBA", (W, H), tuple(LEFT_C) + (255,))
    left.putalpha(tint)
    right = Image.new("RGBA", (W, H), tuple(RIGHT_C) + (255,))
    right.putalpha(ImageChops.invert(tint).point(lambda v: 60 if v > 200 else 0))
    img.alpha_composite(left)
    img.alpha_composite(right)
    return img


def _bolt(rnd):
    m = Image.new("L", (W, H), 0)
    x, y = W // 2 + rnd.randint(-20, 20), 0
    pts = [(x, y)]
    while y < H:
        y += rnd.randint(22, 40)
        x += rnd.randint(-26, 26)
        pts.append((x, y))
    ImageDraw.Draw(m).line(pts, fill=255, width=4)
    return neon.glow(m, (200, 220, 255), 6)


def versus_gif(name1: str, name2: str, av1: bytes | None, av2: bytes | None, subtitle: str, seed=0) -> bytes:
    rnd = random.Random(seed)
    bg = _background()
    p1 = _portrait(av1, LEFT_C, "ghost")
    p2 = _portrait(av2, RIGHT_C, "skull")
    size1 = neon.fit_text(name1.upper(), 30, 250)
    size2 = neon.fit_text(name2.upper(), 30, 250)
    n1 = _neon_layer((W, H), name1.upper(), (170, 244), size1, tuple(LEFT_C), "mm")
    n2 = _neon_layer((W, H), name2.upper(), (W - 170, 244), size2, tuple(RIGHT_C), "mm")
    sub = _neon_layer((W, H), subtitle, (W // 2, 282), neon.fit_text(subtitle, 18, 420), tuple(neon.YELLOW), "mm")
    frames, durations = [], []
    total = 16
    for f in range(total):
        img = bg.copy()
        t = min(1.0, f / 6)
        ease = 1 - (1 - t) ** 3
        y = 40
        img.alpha_composite(p1, (round(-p1.width + (170 - p1.width / 2 + p1.width) * ease), y))
        img.alpha_composite(p2, (round(W - (W - (W - 170 - p2.width / 2)) * ease), y))
        if f >= 6:
            img.alpha_composite(n1)
            img.alpha_composite(n2)
            img.alpha_composite(sub)
        if f >= 7:
            k = f - 7
            size = 120 if k == 0 else (96 + round(6 * math.sin(k * 1.3)))
            vs = _neon_layer((W, H), "VS", (W // 2, 128), size, tuple(neon.YELLOW), "mm")
            img.alpha_composite(vs)
        if f in (7, 8, 12):
            img.alpha_composite(_bolt(rnd))
        if f == 7:
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 70)))
        frames.append(img)
        durations.append(60 if f < 7 else 110)
    durations[-1] = 2000
    return _gif_once(frames, durations)
