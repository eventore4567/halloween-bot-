"""La Machine hantée: a neon slot machine whose three reels spin and stop one by one."""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import neon
from .canvas import png_bytes
from .cards import _gif_once, _neon_layer

W, H = 640, 360
REELS = (190, 320, 450)  # x centres
MID = 196  # y of the payline
STEP = 84  # distance between two symbols on a reel
WIN_W, WIN_H = 112, 214
ICON = 70


def _neon_text(img, text, xy, size, color):
    img.alpha_composite(_neon_layer(img.size, text, tuple(xy), size, tuple(color), "mm"))


@lru_cache(maxsize=64)
def _symbol(name: str, color: tuple, blur: int = 0) -> Image.Image:
    icon = neon.icon_light(name, ICON, color)
    if blur:  # vertical motion blur while the reel spins
        icon = icon.filter(ImageFilter.GaussianBlur((0.5, blur)))
    return icon


@lru_cache(maxsize=1)
def _cabinet() -> Image.Image:
    img = neon.wall(W, H, 3).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 10, 120)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((96, 20, W - 96, H - 16), 34, fill=(24, 10, 30, 255))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (96, 20, W - 96, H - 16), 34, 4), neon.PURPLE, 6))
    _neon_text(img, "MACHINE HANTÉE", (W / 2, 52), 30, neon.PINK)
    for x in REELS:
        box = (x - WIN_W // 2, MID - WIN_H // 2, x + WIN_W // 2, MID + WIN_H // 2)
        d.rounded_rectangle(box, 16, fill=(10, 4, 14, 255))
        img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), box, 16, 3), neon.CYAN, 3))
    # lever
    d.line((W - 70, 120, W - 70, 230), fill=(90, 70, 110), width=8)
    knob = Image.new("L", (W, H), 0)
    ImageDraw.Draw(knob).ellipse((W - 86, 96, W - 54, 128), fill=255)
    img.alpha_composite(neon.glow(knob, neon.RED, 5))
    return img


def _reel_mask(x):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((x - WIN_W // 2 + 3, MID - WIN_H // 2 + 3, x + WIN_W // 2 - 3,
                                         MID + WIN_H // 2 - 3), 14, fill=255)
    return m


@lru_cache(maxsize=1)
def _masks():
    return [_reel_mask(x) for x in REELS]


def _draw_reel(layer, x, strip, pos, colors, speed):
    """``pos`` is the (fractional) index of the symbol on the payline."""
    blur = 0 if speed < 0.25 else (4 if speed < 0.6 else 9)
    base = math.floor(pos)
    for i in range(base - 2, base + 3):
        name = strip[i % len(strip)]
        y = MID + (i - pos) * STEP
        icon = _symbol(name, colors[name], blur)
        layer.alpha_composite(icon, (round(x - icon.width / 2), round(y - icon.height / 2)))


def _frame(strips, positions, speeds, colors, flash=None, label=None):
    img = _cabinet().copy()
    reels = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for k, x in enumerate(REELS):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _draw_reel(layer, x, strips[k], positions[k], colors, speeds[k])
        clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        clipped.paste(layer, (0, 0), _masks()[k])
        reels.alpha_composite(clipped)
    img.alpha_composite(reels)
    line = Image.new("L", (W, H), 0)
    ImageDraw.Draw(line).line((REELS[0] - WIN_W // 2 - 14, MID, REELS[-1] + WIN_W // 2 + 14, MID), fill=255, width=2)
    img.alpha_composite(neon.dim(neon.glow(line, flash or neon.RED, 3), 1.0 if flash else 0.45))
    if label:
        _neon_text(img, label, (W / 2, H - 46), 30, flash or neon.YELLOW)
    return img


def _strips(result, symbols, rnd):
    strips = []
    for k, name in enumerate(result):
        strip = [rnd.choice(symbols) for _ in range(24)]
        strip[-1] = name  # the payline symbol once stopped
        for j in range(len(strip) - 1):
            if strip[j] == strip[j + 1]:
                strip[j] = symbols[(symbols.index(strip[j]) + 1) % len(symbols)]
        strips.append(strip)
    return strips


def spin_frames(result: tuple, symbols: list[str], colors: dict, label: str | None, win_color=None,
                suspense=False, seed=0):
    rnd = random.Random(seed)
    strips = _strips(result, symbols, rnd)
    end = len(strips[0]) - 1
    stops = [14, 20, 30 if suspense else 26]
    total = stops[-1] + 2
    frames, durations = [], []
    for f in range(total + 1):
        positions, speeds = [], []
        for k in range(3):
            t = min(1.0, f / stops[k])
            # fast spin that brakes, with a little bounce at the end
            eased = 1 - (1 - t) ** 3
            pos = end * eased
            if t >= 1:
                after = f - stops[k]
                pos = end + (0.12 * math.sin(after * 2.2) * math.exp(-after * 0.9) if after < 4 else 0)
            speed = 3 * (1 - t) ** 2 * end / stops[k] if t < 1 else 0
            positions.append(pos)
            speeds.append(speed)
        frames.append(_frame(strips, positions, speeds, colors))
        durations.append(55 if f < stops[1] else (90 if suspense else 60))
    final = [end] * 3
    if win_color:
        for k in range(6):
            frames.append(_frame(strips, final, [0, 0, 0], colors, flash=win_color if k % 2 == 0 else neon.WHITE,
                                 label=label))
            durations.append(160)
    still = _frame(strips, final, [0, 0, 0], colors, flash=win_color, label=label)
    frames.append(still)
    durations.append(1400)
    return frames, durations, still


def spin_gif(result, symbols, colors, label=None, win_color=None, suspense=False, seed=0):
    """GIF bytes, play time in seconds, and a PNG of the final state."""
    frames, durations, still = spin_frames(result, symbols, colors, label, win_color, suspense, seed)
    return _gif_once(frames, durations), sum(durations) / 1000, png_bytes(still.convert("RGB"))
