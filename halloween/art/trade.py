"""Card trade animation: both hands of cards fly across and swap owners in a burst of sparks."""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .cards import _gif_once, _neon_layer, card_face

W, H = 680, 330
CARD_W, CARD_H = 112, 157


@lru_cache(maxsize=64)
def small_card(key: str) -> Image.Image:
    from ..content.games import CARD, CARDS, RARITIES
    card = CARD[key]
    number = [c["key"] for c in CARDS].index(key) + 1
    return card_face(card, RARITIES[card["rarity"]], number, len(CARDS)).resize((CARD_W, CARD_H), Image.LANCZOS)


@lru_cache(maxsize=4)
def _bg():
    img = neon.wall(W, H, 2).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 150)))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (12, 10, W - 12, H - 10), 26, 4), neon.YELLOW, 5))
    return img


def _hand(img, keys, cx, cy, tilt=1.0):
    """Up to 3 cards fanned around (cx, cy)."""
    n = len(keys)
    for i, key in enumerate(keys):
        a = (i - (n - 1) / 2) * 12 * tilt
        card = small_card(key).rotate(-a, expand=True, resample=Image.BICUBIC)
        dx = (i - (n - 1) / 2) * 34
        img.alpha_composite(card, (round(cx + dx - card.width / 2), round(cy - card.height / 2 + abs(a) * 0.8)))


def trade_gif(name_a: str, name_b: str, give: list[str], take: list[str], candies: int = 0, seed: int = 0) -> bytes:
    rnd = random.Random(seed)
    left, right = (150, 175), (530, 175)
    sparks = [(rnd.uniform(0, math.tau), rnd.uniform(3, 9)) for _ in range(30)]
    frames, durations = [], []
    total = 22
    for f in range(total + 1):
        img = _bg().copy()
        t = min(1.0, f / 16)
        e = t * t * (3 - 2 * t)
        # the two hands cross each other along arcs
        ax = left[0] + (right[0] - left[0]) * e
        ay = left[1] - 60 * math.sin(math.pi * e)
        bx = right[0] + (left[0] - right[0]) * e
        by = right[1] + 40 * math.sin(math.pi * e)
        if give:
            _hand(img, give, ax, ay)
        if take:
            _hand(img, take, bx, by)
        if 7 <= f <= 14:  # sparks where they cross
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            k = f - 7
            for ang, v in sparks:
                r = v * (k + 1)
                x, y = W / 2 + r * math.cos(ang), 175 + r * math.sin(ang)
                od.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 230, 140, max(0, 255 - 30 * k)))
            img.alpha_composite(over)
        img.alpha_composite(_neon_layer((W, H), name_a.upper()[:16], (left[0], 300), 18, tuple(neon.CYAN), "mm"))
        img.alpha_composite(_neon_layer((W, H), name_b.upper()[:16], (right[0], 300), 18, tuple(neon.PINK), "mm"))
        if f >= 16:
            img.alpha_composite(_neon_layer((W, H), "ÉCHANGE CONCLU !", (W // 2, 40), 34, tuple(neon.YELLOW), "mm"))
            if candies:
                img.alpha_composite(_neon_layer((W, H), f"+ {candies} BONBONS", (W // 2, 78), 18, tuple(neon.PINK), "mm"))
        frames.append(img)
        durations.append(70)
    durations[-1] = 2000
    return _gif_once(frames, durations)


def offer_png(name_a: str, name_b: str, give: list[str], take: list[str], candies: int = 0) -> bytes:
    from .canvas import png_bytes
    img = _bg().copy()
    if give:
        _hand(img, give, 150, 175)
    if take:
        _hand(img, take, 530, 175)
    arrows = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(arrows)
    cx = W // 2
    d.line((cx - 50, 160, cx + 50, 160), fill=255, width=5)
    d.line((cx + 50, 160, cx + 32, 146), fill=255, width=5)
    d.line((cx + 50, 160, cx + 32, 174), fill=255, width=5)
    d.line((cx + 50, 192, cx - 50, 192), fill=255, width=5)
    d.line((cx - 50, 192, cx - 32, 178), fill=255, width=5)
    d.line((cx - 50, 192, cx - 32, 206), fill=255, width=5)
    img.alpha_composite(neon.glow(arrows, neon.YELLOW, 4))
    img.alpha_composite(_neon_layer((W, H), name_a.upper()[:16], (150, 300), 18, tuple(neon.CYAN), "mm"))
    img.alpha_composite(_neon_layer((W, H), name_b.upper()[:16], (530, 300), 18, tuple(neon.PINK), "mm"))
    img.alpha_composite(_neon_layer((W, H), "PROPOSITION D'ÉCHANGE", (W // 2, 40), 28, tuple(neon.YELLOW), "mm"))
    if candies:
        img.alpha_composite(_neon_layer((W, H), f"+ {candies} BONBONS", (150, 80), 16, tuple(neon.PINK), "mm"))
    return png_bytes(img.convert("RGB"))
