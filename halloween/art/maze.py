"""Neon picture of the haunted labyrinth, with fog of war around the player."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import neon
from .canvas import png_bytes
from .cards import _neon_layer
from ..content.maze import N

CELL = 42
OX, OY = 22, 22
W, H = 640, N * CELL + 2 * OY
SIDE = OX + N * CELL + 30  # x of the side panel


def _center(cell):
    return OX + cell[0] * CELL + CELL // 2, OY + cell[1] * CELL + CELL // 2


@lru_cache(maxsize=8)
def _walls(passages: frozenset) -> Image.Image:
    """The whole maze drawn once in neon (cached per maze)."""
    img = neon.wall(W, H, 5).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 150)))
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    x1, y1 = OX + N * CELL, OY + N * CELL
    for x in range(N):
        for y in range(N):
            px, py = OX + x * CELL, OY + y * CELL
            if x + 1 < N and ((x, y), (x + 1, y)) not in passages:
                d.line((px + CELL, py, px + CELL, py + CELL), fill=255, width=3)
            if y + 1 < N and ((x, y), (x, y + 1)) not in passages:
                d.line((px, py + CELL, px + CELL, py + CELL), fill=255, width=3)
    d.rectangle((OX, OY, x1, y1), outline=255, width=3)
    img.alpha_composite(neon.glow(m, neon.PURPLE, 4))
    return img


def _icon(name, color, size=34):
    return neon.icon_light(name, size, color)


def _put(img, icon, cell):
    cx, cy = _center(cell)
    img.alpha_composite(icon, (cx - icon.width // 2, cy - icon.height // 2))


def render(maze, player, seen: set, has_key: bool, steps: int, max_steps: int, candies: int,
           caught=False, escaped=False, reveal=False) -> bytes:
    img = _walls(frozenset(maze.passages)).copy()
    # exit door, glowing green once the key is found
    ex, ey = _center(maze.exit)
    door = Image.new("L", (W, H), 0)
    ImageDraw.Draw(door).rounded_rectangle((ex - 14, ey - 16, ex + 14, ey + 16), 6, outline=255, width=3)
    img.alpha_composite(neon.glow(door, neon.GREEN if has_key else neon.RED, 4))
    if not has_key:
        _put(img, _icon("key", neon.YELLOW), maze.key)
    if maze.candle:
        _put(img, _icon("candle", neon.ORANGE, 30), maze.candle)
    for c in maze.candies:
        _put(img, _icon("candy", neon.PINK, 26), c)
    _put(img, _icon("ghost", neon.WHITE if not caught else neon.RED, 36), maze.ghost)
    _put(img, _icon("pumpkin_lit", neon.CYAN if not escaped else neon.GREEN, 34), player)
    if not reveal:
        # fog of war: clear around the player, dim where already explored, dark elsewhere
        fog = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(fog)
        d.rectangle((OX - 6, OY - 6, OX + N * CELL + 6, OY + N * CELL + 6), fill=228)
        for c in seen:
            px, py = OX + c[0] * CELL, OY + c[1] * CELL
            d.rectangle((px, py, px + CELL, py + CELL), fill=105)
        px, py = _center(player)
        r = int(CELL * 2.6)
        d.ellipse((px - r, py - r, px + r, py + r), fill=0)
        fog = fog.filter(ImageFilter.GaussianBlur(10))
        dark = Image.new("RGBA", (W, H), (4, 2, 8, 255))
        dark.putalpha(fog)
        img.alpha_composite(dark)
        _put(img, _icon("pumpkin_lit", neon.CYAN, 34), player)
    # side panel
    sx = SIDE + (W - SIDE) // 2
    img.alpha_composite(_neon_layer((W, H), "LABYRINTHE", (sx, 44), 26, neon.PURPLE, "mm"))
    key = _icon("key", neon.YELLOW if has_key else (90, 80, 110), 46)
    img.alpha_composite(key, (sx - key.width // 2, 92 - key.height // 2))
    img.alpha_composite(_neon_layer((W, H), "CLÉ TROUVÉE" if has_key else "CLÉ ?", (sx, 132), 18,
                                    neon.YELLOW if has_key else (150, 140, 170), "mm"))
    candy = _icon("candy", neon.PINK, 40)
    img.alpha_composite(candy, (sx - candy.width // 2, 184 - candy.height // 2))
    img.alpha_composite(_neon_layer((W, H), f"+{candies}", (sx, 222), 22, neon.PINK, "mm"))
    left = max(0, max_steps - steps)
    img.alpha_composite(_neon_layer((W, H), "PAS", (sx, 280), 18, neon.CYAN, "mm"))
    img.alpha_composite(_neon_layer((W, H), str(left), (sx, 314), 32, neon.CYAN if left > 10 else neon.RED, "mm"))
    if caught or escaped:
        text, color = ("ATTRAPÉ !", neon.RED) if caught else ("ÉVADÉ !", neon.GREEN)
        img.alpha_composite(_neon_layer((W, H), text, (sx, 370), 24, color, "mm"))
    return png_bytes(img.convert("RGB"))
