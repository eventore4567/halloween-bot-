"""Animated habitat of a haunted pet: it floats, its aura pulses, sparks fly; it grows with its stage."""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import banner_gif_bytes, font
from .cards import _neon_layer

W, H = 680, 340
FRAMES = 14
SIZES = [96, 124, 150, 170]  # by evolution stage


@lru_cache(maxsize=8)
def _habitat(color: tuple) -> Image.Image:
    img = neon.wall(W, H, 3).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 140)))
    d = ImageDraw.Draw(img)
    d.ellipse((60, 262, 360, 318), fill=(24, 12, 30, 255))
    rim = Image.new("L", (W, H), 0)
    ImageDraw.Draw(rim).ellipse((60, 262, 360, 318), outline=255, width=3)
    img.alpha_composite(neon.glow(rim, color, 4))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (12, 10, W - 12, H - 10), 28, 4), neon.PURPLE, 5))
    return img


def _bar(img, x, y, w, value, color, label):
    d = ImageDraw.Draw(img)
    d.text((x, y - 4), label, font=font("body", 16, "Bold"), fill=(220, 210, 240), anchor="ls")
    d.rounded_rectangle((x, y + 4, x + w, y + 18), radius=7, fill=(40, 26, 52))
    if value > 0:
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((x, y + 4, x + max(14, w * value), y + 18), radius=7, fill=255)
        img.alpha_composite(neon.glow(m, color, 3))


def pet_gif(species_icon: str, color: tuple, stage_idx: int, name: str, stage_name: str, level: int,
            hunger: float, joy: float, xp_ratio: float, seed: int = 0) -> bytes:
    rnd = random.Random(seed)
    base = _habitat(tuple(color)).copy()
    size = SIZES[stage_idx]
    nm = name.upper()
    base.alpha_composite(_neon_layer((W, H), nm, (520, 50), neon.fit_text(nm, 30, 280), tuple(color), "mm"))
    base.alpha_composite(_neon_layer((W, H), f"{stage_name.upper()} · NIV. {level}", (520, 88), 18,
                                     tuple(neon.YELLOW), "mm"))
    _bar(base, 400, 140, 240, hunger / 100, neon.ORANGE, "Ventre")
    _bar(base, 400, 196, 240, joy / 100, neon.PINK, "Joie")
    _bar(base, 400, 252, 240, xp_ratio, neon.CYAN, "Expérience")
    sparks = [(rnd.uniform(80, 340), rnd.uniform(110, 260), rnd.uniform(0, 1)) for _ in range(10 + 4 * stage_idx)]
    nframes = max(1, neon.icon_frames(species_icon))
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = base.copy()
        bob = 10 * math.sin(t * math.tau)
        cx, cy = 210, 180 + bob
        aura = Image.new("L", (W, H), 0)
        r = size * (0.62 + 0.05 * math.sin(t * math.tau * 2)) + 8 * stage_idx
        ImageDraw.Draw(aura).ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=2 + stage_idx)
        img.alpha_composite(neon.dim(neon.glow(aura, color, 6 + 2 * stage_idx), 0.35 + 0.15 * stage_idx))
        icon = neon.icon_light(species_icon, size, tuple(color), int(t * nframes) % nframes)
        img.alpha_composite(icon, (round(cx - icon.width / 2), round(cy - icon.height / 2)))
        if stage_idx == 3:  # legendary: a crown floats above
            crown = neon.icon_light("crown", 54, neon.YELLOW)
            img.alpha_composite(crown, (round(cx - crown.width / 2), round(cy - size * 0.62 - crown.height / 2)))
        over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(over)
        for sx, sy, ph in sparks:  # rising sparks
            y = sy - ((t + ph) % 1) * 60
            a = int(255 * (1 - (t + ph) % 1))
            d.ellipse((sx - 2, y - 2, sx + 2, y + 2), fill=tuple(color) + (a,))
        # shadow on the ground follows the bob
        sw = 54 + stage_idx * 12 - bob
        d.ellipse((cx - sw, 288 - 8, cx + sw, 288 + 8), fill=(0, 0, 0, 110))
        img.alpha_composite(over)
        frames.append(img)
    return banner_gif_bytes(frames, duration=90)
