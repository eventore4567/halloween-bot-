"""Motus des ombres: neon letter grid, the newest row flips tile by tile."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import font, png_bytes
from .cards import _gif_once, _neon_layer

W = 700
TILE, GAP = 58, 8
TOP = 84
TRIES = 6
H = TOP + TRIES * (TILE + GAP) + 18

FILL = {"good": (30, 120, 60), "near": (24, 14, 30), "miss": (30, 24, 38), "empty": (16, 10, 22), "hint": (16, 10, 22)}


def _x0(length):
    return (W - (length * TILE + (length - 1) * GAP)) // 2


PAD = 12


@lru_cache(maxsize=512)
def _tile_img(letter: str, state: str, squash: float) -> Image.Image:
    """One glowing tile on its own small canvas; ``squash`` (0..1) flattens it for the flip."""
    size = TILE + 2 * PAD
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cy = size / 2
    half = TILE / 2 * max(0.06, squash)
    box = (PAD, round(cy - half), PAD + TILE, round(cy + half))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=10, fill=FILL[state])
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=10, outline=255, width=3)
    color = {"good": neon.GREEN, "near": neon.ORANGE, "miss": (90, 80, 110), "empty": neon.PURPLE,
             "hint": neon.PURPLE}[state]
    img.alpha_composite(neon.dim(neon.glow(m, color, 3), 0.9 if state in ("good", "near") else 0.45))
    if state == "near" and squash > 0.5:
        ring = Image.new("L", img.size, 0)
        r = TILE / 2 - 7
        ImageDraw.Draw(ring).ellipse((cy - r, cy - r * squash, cy + r, cy + r * squash), outline=255, width=3)
        img.alpha_composite(neon.glow(ring, neon.ORANGE, 3))
    if letter and squash > 0.35:
        fill = (255, 255, 255) if state in ("good", "near") else ((150, 140, 170) if state == "hint" else (190, 180, 210))
        d = ImageDraw.Draw(img)
        d.text((cy, cy + 1), letter, font=font("neon", 34), fill=fill, anchor="mm")
    return img


def _tile(img, box, letter, state, squash=1.0):
    tile = _tile_img(letter, state, round(squash, 2))
    img.alpha_composite(tile, (box[0] - PAD, box[1] - PAD))


@lru_cache(maxsize=4)
def _wall(title):
    img = neon.wall(W, H, 1).copy()
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 120)))
    img.alpha_composite(_neon_layer((W, H), title, (W // 2, 42), 34, neon.CYAN, "mm"))
    return img


def _base(length, title):
    return _wall(title).copy()


def _grid(rows, length, first, flip_row=None, flip_t=None, title="MOTUS DES OMBRES"):
    """``rows``: finished guesses as lists of (letter, state)."""
    img = _base(length, title)
    x0 = _x0(length)
    for r in range(TRIES):
        y = TOP + r * (TILE + GAP)
        for c in range(length):
            box = (x0 + c * (TILE + GAP), y, x0 + c * (TILE + GAP) + TILE, y + TILE)
            if r < len(rows):
                letter, state = rows[r][c]
                if r == flip_row and flip_t is not None:
                    local = flip_t * (length + 1) - c  # tiles flip one after the other
                    if local <= 0:
                        _tile(img, box, letter, "empty")
                    elif local < 1:
                        squash = round(abs(1 - 2 * local) * 6) / 6
                        _tile(img, box, letter, "empty" if local < 0.5 else state, squash)
                    else:
                        _tile(img, box, letter, state)
                else:
                    _tile(img, box, letter, state)
            elif r == len(rows):
                _tile(img, box, first if c == 0 else "·", "hint")
            else:
                _tile(img, box, "", "empty")
    return img


def grid_png(rows, length, first) -> bytes:
    return png_bytes(_grid(rows, length, first).convert("RGB"))


def flip_gif(rows, length, first) -> tuple[bytes, float]:
    """The last row of ``rows`` flips tile by tile."""
    steps = 3 * (length + 1)
    frames = [_grid(rows, length, first, len(rows) - 1, k / steps) for k in range(steps + 1)]
    durations = [45] * steps + [1500]
    return _gif_once(frames, durations), sum(durations) / 1000
