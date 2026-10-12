"""La Planche Ouija: a neon spirit board where a planchette glides from letter to letter.

``spell_gif`` plays once: the planchette visits every letter of a hidden word
(the letter under the lens flares pink), then rests on « AU REVOIR ».
``board_png`` is the same board at rest, shown while the player answers.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import neon
from .cards import _gif_once

W, H = 680, 400
CX, CY = 340, 384
GOODBYE = (340, 352)
REST = (340, 262)
LETTER_COLOR = (255, 226, 150)


def _arc(letters: str, radius: int, start: float, end: float):
    out = {}
    for k, ch in enumerate(letters):
        a = math.radians(start + (end - start) * k / (len(letters) - 1))
        out[ch] = (round(CX + radius * math.cos(a)), round(CY - radius * math.sin(a)))
    return out


POSITIONS = {**_arc("ABCDEFGHIJKLM", 264, 160, 20), **_arc("NOPQRSTUVWXYZ", 196, 154, 26)}
SIZES = {ch: (34 if ch <= "M" else 30) for ch in POSITIONS}


@lru_cache(maxsize=None)
def _letter_glow(ch: str, color: tuple, radius: float) -> Image.Image:
    m = neon.text_mask((W, H), ch, SIZES[ch], POSITIONS[ch])
    return neon.glow(m, color, radius)


@lru_cache(maxsize=4)
def _board(seed: int) -> Image.Image:
    img = neon.wall(W, H, seed % 5).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 10, 120)))
    plate = Image.new("L", (W, H), 0)
    ImageDraw.Draw(plate).rounded_rectangle((26, 18, W - 26, H - 14), 46, fill=150)
    wood = Image.new("RGBA", (W, H), (34, 16, 22, 255))
    wood.putalpha(plate)
    img.alpha_composite(wood)
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (26, 18, W - 26, H - 14), 46, 4), neon.PURPLE, 6))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (40, 32, W - 40, H - 28), 36, 2), neon.PURPLE, 3))
    for word, x in (("OUI", 150), ("NON", W - 150)):
        img.alpha_composite(neon.glow(neon.text_mask((W, H), word, 30, (x, 66)), neon.GREEN if word == "OUI" else neon.RED, 5))
    for name, color, x in (("moon", neon.YELLOW, 78), ("skull", neon.WHITE, W - 78)):
        icon = neon.icon_light(name, 46, color)
        img.alpha_composite(icon, (x - icon.width // 2, 66 - icon.height // 2))
    for ch in POSITIONS:
        img.alpha_composite(neon.dim(_letter_glow(ch, LETTER_COLOR, 3.5), 0.7))
    img.alpha_composite(neon.glow(neon.text_mask((W, H), "AU REVOIR", 24, GOODBYE), neon.WHITE, 4))
    return img


@lru_cache(maxsize=1)
def _planchette() -> tuple[Image.Image, tuple[int, int]]:
    """Heart-shaped pointer with a round lens; returns the image and the lens centre."""
    s = 4
    w, h = 96, 118
    body = Image.new("L", (w * s, h * s), 0)
    d = ImageDraw.Draw(body)
    d.ellipse((4 * s, 26 * s, 92 * s, 104 * s), fill=255)
    d.polygon([(48 * s, 0), (16 * s, 44 * s), (80 * s, 44 * s)], fill=255)
    d.ellipse((30 * s, 92 * s, 66 * s, 116 * s), fill=255)
    body = body.resize((w, h), Image.LANCZOS)
    edge = ImageChops.subtract(body, body.filter(ImageFilter.MinFilter(5)))
    lens_c = (48, 60)
    ring = Image.new("L", (w, h), 0)
    ImageDraw.Draw(ring).ellipse((lens_c[0] - 20, lens_c[1] - 20, lens_c[0] + 20, lens_c[1] + 20), outline=255, width=3)
    shade = Image.new("RGBA", (w, h), (20, 6, 18, 0))
    hole = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hole).ellipse((lens_c[0] - 18, lens_c[1] - 18, lens_c[0] + 18, lens_c[1] + 18), fill=255)
    shade.putalpha(Image.eval(Image.composite(Image.new("L", (w, h), 0), body, hole), lambda v: int(v * 0.75)))
    pad = 20
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    out.alpha_composite(shade, (pad, pad))
    lines = Image.new("L", out.size, 0)
    lines.paste(Image.eval(edge, lambda v: 255 if v > 90 else 0), (pad, pad))
    lines.paste(ring, (pad, pad), ring)
    out.alpha_composite(neon.glow(lines, neon.PINK, 4))
    return out, (lens_c[0] + pad, lens_c[1] + pad)


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def _frame(base, pos, highlight=None, candle=0, wobble=(0, 0)):
    img = base.copy()
    if highlight:
        img.alpha_composite(_letter_glow(highlight, neon.PINK, 7))
    n = max(1, neon.icon_frames("candle"))
    for k, x in enumerate((44, W - 98)):
        c = neon.icon_light("candle", 54, neon.ORANGE, (candle + k) % n)
        img.alpha_composite(c, (x, H - 92))
    p, (lx, ly) = _planchette()
    img.alpha_composite(p, (round(pos[0] - lx + wobble[0]), round(pos[1] - ly + wobble[1])))
    return img


def letters_of(word: str) -> str:
    return "".join(ch for ch in word.upper() if ch in POSITIONS)


def spell_frames(word: str, hold_ms: int = 600, seed: int = 0):
    """Frames and durations of the planchette spelling ``word`` (letters only)."""
    rnd = random.Random(seed)
    base = _board(seed)
    frames, durations = [], []
    pos, tick = REST, 0
    for _ in range(3):  # the candles come alive before the spirit answers
        frames.append(_frame(base, pos, candle=tick))
        durations.append(260)
        tick += 1
    stops = [(POSITIONS[ch], ch) for ch in letters_of(word)] + [(GOODBYE, None)]
    prev = None
    for target, ch in stops:
        path = []
        if ch is not None and ch == prev:  # same letter twice: the spirit circles back
            path.append((target[0] + 34, target[1] + 26))
        path.append(target)
        for point in path:
            steps = 4
            for s in range(1, steps + 1):
                t = _ease(s / steps)
                xy = (pos[0] + (point[0] - pos[0]) * t, pos[1] + (point[1] - pos[1]) * t)
                frames.append(_frame(base, xy, candle=tick, wobble=(rnd.uniform(-2, 2), rnd.uniform(-2, 2))))
                durations.append(55)
                tick += 1
            pos = point
        frames.append(_frame(base, pos, highlight=ch, candle=tick))
        durations.append(hold_ms if ch else 1600)
        tick += 1
        prev = ch
    return frames, durations


def spell_gif(word: str, hold_ms: int = 600, seed: int = 0) -> tuple[bytes, float]:
    """The GIF and how long it plays, in seconds."""
    frames, durations = spell_frames(word, hold_ms, seed)
    return _gif_once(frames, durations), sum(durations) / 1000


def board_png(seed: int = 0, highlight: str | None = None) -> bytes:
    img = _frame(_board(seed), GOODBYE, highlight=highlight).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
