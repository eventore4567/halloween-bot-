"""Le Bonneteau des Citrouilles: a candy hides under one of three neon pumpkins, then they shuffle.

``shuffle_gif`` plays once: the pumpkin hiding the candy lifts, drops, then the
pumpkins swap places along arcs, faster and faster. ``still_png`` shows the
three numbered pumpkins at rest; ``reveal_png`` lifts the chosen one (and the
right one).
"""
from __future__ import annotations

import math
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from . import neon
from .cards import _gif_once

W, H = 680, 340
SLOTS = (170, 340, 510)
GROUND = 250  # y of the pumpkins' base
CUP = 128
LIFT = 92


@lru_cache(maxsize=1)
def _table() -> Image.Image:
    img = neon.wall(W, H, 2).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 10, 110)))
    d = ImageDraw.Draw(img)
    d.ellipse((40, GROUND - 26, W - 40, GROUND + 60), fill=(24, 12, 30, 255))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (14, 12, W - 14, H - 12), 30, 4), neon.ORANGE, 6))
    rim = Image.new("L", (W, H), 0)
    ImageDraw.Draw(rim).ellipse((40, GROUND - 26, W - 40, GROUND + 60), outline=255, width=3)
    img.alpha_composite(neon.glow(rim, neon.PURPLE, 4))
    return img


@lru_cache(maxsize=1)
def _cup():
    """Neon pumpkin with a dark solid body, so the one in front hides the one behind."""
    from .emoji_art import render_frame
    light = neon.icon_light("pumpkin_lit", CUP, neon.ORANGE)
    pad = CUP // 4
    alpha = render_frame("pumpkin_lit", 0.0, 128).resize((CUP, CUP), Image.LANCZOS).getchannel("A")
    body = Image.new("RGBA", light.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", (CUP, CUP), (28, 12, 8, 255))
    solid.putalpha(alpha.point(lambda v: 255 if v > 100 else 0))
    body.alpha_composite(solid, (pad, pad))
    body.alpha_composite(light)
    return body


@lru_cache(maxsize=1)
def _candy():
    return neon.icon_light("candy", 58, neon.PINK)


def _shadow(img, x, lift):
    d = ImageDraw.Draw(img)
    r = 46 - lift * 0.18
    d.ellipse((x - r, GROUND + 4 - r * 0.22, x + r, GROUND + 4 + r * 0.22), fill=(0, 0, 0, 150))


def _paste_center(img, layer, x, y_bottom):
    img.alpha_composite(layer, (round(x - layer.width / 2), round(y_bottom - layer.height + layer.height * 0.2)))


def _scene(cups, candy_x=None, numbers=False, highlight=None):
    """``cups``: list of (x, lift) drawn back to front."""
    img = _table().copy()
    for x, lift in cups:
        _shadow(img, x, lift)
    if candy_x is not None:
        _paste_center(img, _candy(), candy_x, GROUND + 6)
    for x, lift in cups:
        _paste_center(img, _cup(), x, GROUND - lift)
    if numbers:
        for k, x in enumerate(SLOTS):
            color = neon.YELLOW if highlight is None or k != highlight else neon.GREEN
            img.alpha_composite(neon.glow(neon.text_mask((W, H), str(k + 1), 34, (x, GROUND + 52)), color, 5))
    return img


def _ease(t):
    return t * t * (3 - 2 * t)


def shuffle_frames(candy_slot: int, swaps: list[tuple[int, int]], steps: int = 6):
    """Frames, durations and the slot the candy ends under."""
    frames, durations = [], []
    rest = [(x, 0) for x in SLOTS]
    frames.append(_scene(rest))
    durations.append(500)
    for k in range(1, 6):  # reveal the candy
        lift = LIFT * _ease(k / 5)
        frames.append(_scene([(x, lift if i == candy_slot else 0) for i, x in enumerate(SLOTS)], SLOTS[candy_slot]))
        durations.append(60)
    durations[-1] = 900
    for k in range(4, -1, -1):
        lift = LIFT * _ease(k / 5)
        frames.append(_scene([(x, lift if i == candy_slot else 0) for i, x in enumerate(SLOTS)],
                             SLOTS[candy_slot] if k else None))
        durations.append(60)
    durations[-1] = 350
    slot = candy_slot
    for a, b in swaps:
        xa, xb = SLOTS[a], SLOTS[b]
        arc = 40 + abs(xa - xb) * 0.18
        for s in range(1, steps + 1):
            t = _ease(s / steps)
            front = (xa + (xb - xa) * t, -arc * 0.25 * math.sin(math.pi * t))  # dips toward the viewer
            back = (xb + (xa - xb) * t, arc * math.sin(math.pi * t))
            others = [(x, 0) for i, x in enumerate(SLOTS) if i not in (a, b)]
            frames.append(_scene(others + [back, front]))
            durations.append(45)
        if slot == a:
            slot = b
        elif slot == b:
            slot = a
    frames.append(_scene(rest, numbers=True))
    durations.append(1500)
    return frames, durations, slot


def shuffle_gif(candy_slot: int, swaps: list[tuple[int, int]], steps: int = 6) -> tuple[bytes, float, int]:
    frames, durations, slot = shuffle_frames(candy_slot, swaps, steps)
    return _gif_once(frames, durations), sum(durations) / 1000, slot


def _png(img) -> bytes:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def still_png() -> bytes:
    return _png(_scene([(x, 0) for x in SLOTS], numbers=True))


def reveal_png(candy_slot: int, chosen: int) -> bytes:
    cups = [(x, LIFT if i in (candy_slot, chosen) else 0) for i, x in enumerate(SLOTS)]
    return _png(_scene(cups, SLOTS[candy_slot], numbers=True, highlight=candy_slot))
