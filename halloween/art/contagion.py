"""La Malédiction contagieuse: the chain of everyone who held the curse, drawn as a neon map of portraits.

``pass_gif``  a cursed orb travels along the chain from the old holder to the new one.
``final_gif`` the curse settles on its last victim (or shatters when the chain is complete).
``map_png``   the chain right now, for /malediction.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import encode_gif, png_bytes
from .cards import _neon_layer
from .versus import _portrait

W, H = 760, 340
NODE = 84  # portrait size on the map
PER_ROW = 6


def node_xy(i: int) -> tuple[float, float]:
    """Snake layout: row 0 left → right, row 1 right → left."""
    row, col = divmod(i, PER_ROW)
    step = (W - 140) / (PER_ROW - 1)
    x = 70 + step * (col if row % 2 == 0 else PER_ROW - 1 - col)
    y = 138 + 112 * row
    return x, y


@lru_cache(maxsize=2)
def _bg() -> Image.Image:
    img = neon.wall(W, H, 4).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (8, 2, 14, 170)))
    m = neon.rounded_frame_mask((W, H), (10, 8, W - 10, H - 8), 24, 4)
    img.alpha_composite(neon.glow(m, neon.PURPLE, 5))
    return img


@lru_cache(maxsize=256)
def _text(text, x, y, size, color) -> Image.Image:
    return _neon_layer((W, H), text, (x, y), size, color, "mm")


def _title(img, text, y, color, size=30):
    img.alpha_composite(_text(text, W // 2, y, neon.fit_text(text, size, W - 60), tuple(color)))


@lru_cache(maxsize=64)
def _links(n: int, color, upto: int | None = None) -> Image.Image:
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    last = n - 1 if upto is None else upto
    for i in range(min(last, n - 1)):
        d.line((*node_xy(i), *node_xy(i + 1)), fill=255, width=4)
    return neon.glow(m, color, 4)


def _portraits(people, color):
    out = []
    for name, avatar in people:
        p = _portrait(avatar, color, "skull").resize((NODE + 24, NODE + 24), Image.LANCZOS)
        out.append((name, p))
    return out


def _draw_nodes(img, nodes, holder: int | None, f: int, lost: bool = False):
    for i, (name, p) in enumerate(nodes):
        x, y = node_xy(i)
        if i == holder:
            pulse = 1.0 + 0.06 * math.sin(f * 0.9)
            size = round(p.width * pulse)
            q = p.resize((size, size), Image.LANCZOS)
            ring = Image.new("L", (W, H), 0)
            r = size / 2 + 6
            ImageDraw.Draw(ring).ellipse((x - r, y - r, x + r, y + r), outline=255, width=5)
            img.alpha_composite(neon.glow(ring, neon.RED, 6))
            img.alpha_composite(q, (round(x - size / 2), round(y - size / 2)))
            skull = _icon("skull_fire" if not lost else "skull", 40, tuple(neon.RED))
            img.alpha_composite(skull, (round(x + size / 2 - 26), round(y - size / 2 - 18)))
        else:
            img.alpha_composite(p, (round(x - p.width / 2), round(y - p.height / 2)))
        label = name.upper()[:11]
        img.alpha_composite(_text(label, round(x), round(y + NODE / 2 + 12), neon.fit_text(label, 14, 110),
                                  tuple(neon.RED if i == holder else neon.WHITE)))


@lru_cache(maxsize=16)
def _icon(name, size, color) -> Image.Image:
    return neon.icon_light(name, size, color)


def _orb(img, x, y, f):
    orb = _icon("skull_fire", 46, tuple(neon.PURPLE))
    img.alpha_composite(orb, (round(x - orb.width / 2), round(y - orb.height / 2 + 3 * math.sin(f))))


def pass_gif(people: list[tuple[str, bytes | None]], seed: int = 0) -> bytes:
    """``people``: the chain in order; the curse goes from the second to last to the last one."""
    rnd = random.Random(seed)
    nodes = _portraits(people, neon.PURPLE)
    n = len(nodes)
    a, b = n - 2, n - 1
    sparks = [(rnd.uniform(0, math.tau), rnd.uniform(3, 8)) for _ in range(24)]
    frames, durations = [], []
    total = 24
    for f in range(total):
        img = _bg().copy()
        img.alpha_composite(_links(n, tuple(neon.PURPLE), a))
        t = min(1.0, f / 12)
        ax, ay = node_xy(a)
        bx, by = node_xy(b)
        if t > 0:  # the new link draws itself behind the orb
            m = Image.new("L", (W, H), 0)
            ImageDraw.Draw(m).line((ax, ay, ax + (bx - ax) * t, ay + (by - ay) * t), fill=255, width=4)
            img.alpha_composite(neon.glow(m, neon.RED, 4))
        _draw_nodes(img, nodes, b if f >= 12 else a, f)
        if f < 13:
            e = t * t * (3 - 2 * t)
            _orb(img, ax + (bx - ax) * e, ay + (by - ay) * e - 40 * math.sin(math.pi * e), f)
        else:  # it hits: sparks around the new holder
            k = f - 12
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for ang, v in sparks:
                r = NODE / 2 + v * (k + 1)
                px, py = bx + r * math.cos(ang), by + r * math.sin(ang)
                od.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(200, 90, 255, max(0, 255 - 22 * k)))
            img.alpha_composite(over)
        _title(img, f"LA MALÉDICTION PASSE À {people[b][0].upper()[:16]} !", 38, neon.PURPLE)
        _title(img, f"MAILLON {n}", 72, neon.RED, 18)
        frames.append(img)
        durations.append(80)
    durations[-1] = 2500
    return encode_gif(frames, durations)


def final_gif(people: list[tuple[str, bytes | None]], broken: bool, seed: int = 0) -> bytes:
    """The end of the chain: the last holder keeps the curse, or the whole chain shatters it."""
    rnd = random.Random(seed)
    nodes = _portraits(people, neon.GREEN if broken else neon.PURPLE)
    n = len(nodes)
    holder = None if broken else n - 1
    shards = [(rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(5, 10)) for _ in range(40)]
    frames, durations = [], []
    for f in range(22):
        img = _bg().copy()
        img.alpha_composite(_links(n, tuple(neon.GREEN if broken else neon.PURPLE)))
        _draw_nodes(img, nodes, holder, f, lost=True)
        if broken:
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for x, y, v in shards:
                yy = (y + f * v * 8) % (H + 20) - 10
                od.polygon([(x, yy), (x + 6, yy + 3), (x + 2, yy + 9)], fill=(150, 255, 170, 220))
            img.alpha_composite(over)
            _title(img, "MALÉDICTION BRISÉE !", 38, neon.GREEN, 34)
            _title(img, f"{n} MAILLONS : TOUTE LA CHAÎNE EST RÉCOMPENSÉE", 72, neon.YELLOW, 18)
        else:
            _title(img, f"{people[-1][0].upper()[:16]} GARDE LA MALÉDICTION…", 38, neon.RED, 32)
            _title(img, f"LA CHAÎNE S'ARRÊTE À {n} MAILLONS", 72, neon.PURPLE, 18)
        frames.append(img)
        durations.append(90)
    durations[-1] = 3000
    return encode_gif(frames, durations)


def map_png(people: list[tuple[str, bytes | None]], minutes_left: int) -> bytes:
    nodes = _portraits(people, neon.PURPLE)
    img = _bg().copy()
    img.alpha_composite(_links(len(nodes), tuple(neon.PURPLE)))
    _draw_nodes(img, nodes, len(nodes) - 1, 0)
    _title(img, "LA MALÉDICTION CONTAGIEUSE", 38, neon.PURPLE, 32)
    _title(img, f"ENCORE {minutes_left} MIN POUR LA REFILER", 72, neon.RED, 18)
    return png_bytes(img.convert("RGB"))
