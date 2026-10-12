"""Animated broom race (GIF that plays once and stops on the winner)."""
from __future__ import annotations

import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import Canvas
from .cards import _gif_once, _neon_text

W, H = 680, 360
LANES = 4
TOP, LANE_H = 64, 62
START_X, FINISH_X = 70, 590


def _rider(color, size=58):
    """A witch on her broom, with a coloured scarf."""
    c = Canvas(size + 40, size + 10, ss=2)
    c.line([(4, size * 0.78), (size + 30, size * 0.62)], (150, 92, 52), 5)
    c.poly([(0, size * 0.66), (14, size * 0.72), (0, size * 0.94)], (220, 180, 90), (60, 40, 20), 2)
    c.line([(size * 0.3, size * 0.8), (size * 0.15, size * 0.95)], tuple(color), 6)
    img = c.result()
    head = neon.icon_light("witch", size - 10, tuple(color))
    img.alpha_composite(head, (16 - head.width // 5, -head.height // 5))
    return img


def progress_curves(winner: int, steps: int, rnd: random.Random):
    """Monotonic progress (0→1) for every lane; the winner crosses first."""
    curves = []
    for lane in range(LANES):
        pos, out = 0.0, []
        for _ in range(steps):
            pos += rnd.uniform(0.4, 1.6)
            out.append(pos)
        curves.append(out)
    finals = {lane: (1.0 if lane == winner else rnd.uniform(0.82, 0.96)) for lane in range(LANES)}
    return [[v / c[-1] * finals[lane] for v in c] for lane, c in enumerate(curves)]


@lru_cache(maxsize=16)
def race_gif(winner: int, names: tuple, colors: tuple, seed: int = 0) -> bytes:
    rnd = random.Random(seed * 10 + winner)
    base = Canvas(W, H, ss=1)
    base.paste(neon.wall(W, H, 2), (0, 0), (W, H))
    _neon_text(base, "COURSE DE BALAIS", (W / 2, 30), 32, neon.GREEN, max_w=W - 80)
    bg = base.result()
    d = ImageDraw.Draw(bg)
    for lane in range(LANES):
        y = TOP + lane * LANE_H
        d.rectangle((0, y, W, y + LANE_H - 6), fill=(18, 12, 22) if lane % 2 else (24, 16, 30))
    for k in range(0, LANE_H * LANES, 12):  # checkered finish line
        for col in range(2):
            fill = (240, 240, 250) if (k // 12 + col) % 2 else (30, 30, 40)
            d.rectangle((FINISH_X + col * 8, TOP + k, FINISH_X + 8 + col * 8, TOP + k + 12), fill=fill)
    for lane, (name, color) in enumerate(zip(names, colors)):
        y = TOP + lane * LANE_H + (LANE_H - 6) // 2
        lab = Canvas(W, H, ss=1)
        lab.img = bg
        _neon_text(lab, f"{lane + 1}", (26, y), 26, color)
    riders = [_rider(c) for c in colors]
    steps = 34
    curves = progress_curves(winner, steps, rnd)
    frames, durations = [], []
    for k in range(steps + 1):
        img = bg.copy()
        for lane in range(LANES):
            p = 0.0 if k == 0 else curves[lane][k - 1]
            x = START_X + (FINISH_X - START_X - 50) * p
            y = TOP + lane * LANE_H - 2 + (2 if (k + lane) % 2 else 0)
            trail = Image.new("RGBA", (int(max(1, x - START_X + 30)), 10), (0, 0, 0, 0))
            ImageDraw.Draw(trail).rectangle((0, 3, trail.width, 7), fill=tuple(colors[lane]) + (90,))
            img.alpha_composite(trail, (START_X - 20, y + 40))
            img.alpha_composite(riders[lane], (int(x), y))
        if k == steps:
            hl = Image.new("RGBA", (W, LANE_H - 6), tuple(colors[winner]) + (50,))
            img.alpha_composite(hl, (0, TOP + winner * LANE_H))
            c = Canvas(W, H, ss=1)
            c.img = img
            _neon_text(c, f"{names[winner].upper()} GAGNE !", (W / 2, H - 22), 30, colors[winner], max_w=W - 60)
        frames.append(img)
        durations.append(110)
    durations[-1] = 60000
    return _gif_once(frames, durations)
