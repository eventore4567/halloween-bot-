"""La Roulette des potions: six neon vials on a shelf, one is poisoned. Drinking is animated."""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import png_bytes
from .cards import _gif_once, _neon_layer

W, H = 680, 320
VIALS = [("potion_red", neon.RED), ("potion_blue", neon.CYAN), ("potion_green", neon.GREEN),
         ("potion_purple", neon.PURPLE), ("potion_gold", neon.YELLOW), ("potion_red", neon.PINK)]
XS = [90 + i * 100 for i in range(6)]
SHELF = 230
SIZE = 92


@lru_cache(maxsize=1)
def _shelf() -> Image.Image:
    img = neon.wall(W, H, 6).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 140)))
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).line((30, SHELF + 8, W - 30, SHELF + 8), fill=255, width=4)
    img.alpha_composite(neon.glow(m, neon.ORANGE, 4))
    for i, x in enumerate(XS):
        img.alpha_composite(_neon_layer((W, H), str(i + 1), (x, SHELF + 38), 24, neon.YELLOW, "mm"))
    return img


@lru_cache(maxsize=32)
def _vial(i: int, state: str) -> Image.Image:
    name, color = VIALS[i]
    if state == "empty":
        return neon.dim(neon.icon_light(name, SIZE, (90, 80, 110)), 0.6)
    if state == "poison":
        return neon.icon_light("skull", SIZE, neon.GREEN)
    return neon.icon_light(name, SIZE, color)


def _scene(states, lift=None, label=None, color=None, flash=0):
    img = _shelf().copy()
    for i, x in enumerate(XS):
        v = _vial(i, states[i])
        dy = 0
        if lift and lift[0] == i:
            dy = lift[1]
        img.alpha_composite(v, (x - v.width // 2, SHELF - v.height + v.height // 6 - dy))
    if flash:
        img.alpha_composite(Image.new("RGBA", (W, H), tuple(color) + (flash,)))
    if label:
        img.alpha_composite(_neon_layer((W, H), label, (W // 2, 40), 34, tuple(color), "mm"))
    return img


def shelf_png(states, label=None, color=None) -> bytes:
    return png_bytes(_scene(states, label=label, color=color or neon.YELLOW).convert("RGB"))


def drink_gif(states, index: int, poisoned: bool, label: str) -> tuple[bytes, float]:
    """The chosen vial rises, shakes, then turns out safe (empty) or poisoned (skull + green flash)."""
    frames, durations = [], []
    for k in range(6):  # rises
        frames.append(_scene(states, (index, 8 * k)))
        durations.append(50)
    for k in range(8):  # suspense shake
        st = list(states)
        frames.append(_scene(st, (index, 40 + round(4 * math.sin(k * 2.1)))))
        durations.append(70 + 15 * k)
    final = list(states)
    final[index] = "poison" if poisoned else "empty"
    color = neon.GREEN if poisoned else neon.YELLOW
    if poisoned:
        for k in range(4):
            frames.append(_scene(final, (index, 40), label, color, flash=90 if k % 2 == 0 else 0))
            durations.append(120)
    frames.append(_scene(final, None, label, color))
    durations.append(1500)
    return _gif_once(frames, durations), sum(durations) / 1000
