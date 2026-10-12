"""Neon connect-four board: pumpkins against potions, discs fall into place."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import png_bytes
from .cards import _gif_once, _neon_layer
from ..content.connect4 import COLS, ROWS

CELL = 66
W = 600
X0 = (W - COLS * CELL) // 2
Y0 = 52
H = Y0 + ROWS * CELL + 22
R = 26
PIECES = {1: ("pumpkin_lit", neon.ORANGE), 2: ("potion_green", neon.GREEN)}


def _center(row, col):
    return X0 + col * CELL + CELL // 2, Y0 + row * CELL + CELL // 2


@lru_cache(maxsize=1)
def _back() -> Image.Image:
    img = neon.wall(W, H, 4).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 160)))
    for c in range(COLS):
        x, _ = _center(0, c)
        img.alpha_composite(_neon_layer((W, H), str(c + 1), (x, 26), 22, neon.YELLOW, "mm"))
    return img


@lru_cache(maxsize=1)
def _front() -> Image.Image:
    box = (X0 - 10, Y0 - 8, X0 + COLS * CELL + 10, Y0 + ROWS * CELL + 8)
    alpha = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(alpha)
    d.rounded_rectangle(box, 22, fill=235)
    rings = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(rings)
    for r in range(ROWS):
        for c in range(COLS):
            x, y = _center(r, c)
            d.ellipse((x - R, y - R, x + R, y + R), fill=0)
            dr.ellipse((x - R - 1, y - R - 1, x + R + 1, y + R + 1), outline=255, width=2)
    panel = Image.new("RGBA", (W, H), (26, 12, 46, 255))
    panel.putalpha(alpha)
    panel.alpha_composite(neon.dim(neon.glow(rings, neon.PURPLE, 2), 0.55))
    panel.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), box, 22, 4), neon.CYAN, 5))
    return panel


@lru_cache(maxsize=4)
def _disc(piece: int, lit: bool = False) -> Image.Image:
    name, color = PIECES[piece]
    size = 2 * R + 24
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size // 2
    ImageDraw.Draw(img).ellipse((c - R + 2, c - R + 2, c + R - 2, c + R - 2), fill=tuple(int(v * 0.22) for v in color) + (255,))
    ring = Image.new("L", (size, size), 0)
    ImageDraw.Draw(ring).ellipse((c - R + 3, c - R + 3, c + R - 3, c + R - 3), outline=255, width=4 if lit else 3)
    img.alpha_composite(neon.glow(ring, neon.WHITE if lit else color, 5 if lit else 3))
    icon = neon.icon_light(name, 34, neon.WHITE if lit else color)
    img.alpha_composite(icon, (c - icon.width // 2, c - icon.height // 2))
    return img


def _scene(board, falling=None, lit=()):
    img = _back().copy()
    for r in range(ROWS):
        for c in range(COLS):
            if board[r][c]:
                d = _disc(board[r][c], (r, c) in lit)
                x, y = _center(r, c)
                img.alpha_composite(d, (x - d.width // 2, y - d.height // 2))
    if falling:
        piece, x, y = falling
        d = _disc(piece)
        img.alpha_composite(d, (round(x - d.width / 2), round(y - d.height / 2)))
    img.alpha_composite(_front())
    return img


def board_png(board, lit=()) -> bytes:
    return png_bytes(_scene(board, lit=set(lit)).convert("RGB"))


def drop_gif(board_before, moves, win_cells=None) -> tuple[bytes, float]:
    """``moves``: [(row, col, piece)] played in order on ``board_before``."""
    board = [row[:] for row in board_before]
    frames, durations = [_scene(board)], [80]
    for row, col, piece in moves:
        x, target = _center(row, col)
        start = Y0 - CELL // 2 - 4
        steps = 4 + row
        for k in range(1, steps + 1):
            t = k / steps
            frames.append(_scene(board, (piece, x, start + (target - start) * t * t)))
            durations.append(40)
        frames.append(_scene(board, (piece, x, target - 7)))  # little bounce
        durations.append(50)
        board[row][col] = piece
        frames.append(_scene(board))
        durations.append(260)
    if win_cells:
        for k in range(6):
            frames.append(_scene(board, lit=set(win_cells) if k % 2 == 0 else ()))
            durations.append(170)
    frames.append(_scene(board, lit=set(win_cells or ())))
    durations.append(1500)
    return _gif_once(frames, durations), sum(durations) / 1000
