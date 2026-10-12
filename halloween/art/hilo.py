"""Plus ou Moins: neon monster cards numbered 1 to 13; the next card flips over."""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import font, png_bytes
from .cards import _gif_once, _neon_layer

W, H = 640, 330
CW, CH = 156, 220
LEFT, RIGHT = (150, 165), (420, 165)  # card centres
MONSTERS = ["candy", "bat", "spider", "pumpkin", "ghost", "skull", "eye", "witch", "mummy", "zombie", "werewolf",
            "vampire", "reaper"]
COLORS = [neon.PINK, neon.PURPLE, neon.GREEN, neon.ORANGE, neon.WHITE, neon.CYAN, neon.GREEN, neon.PINK,
          neon.YELLOW, neon.GREEN, neon.ORANGE, neon.RED, neon.PURPLE]


def label(value: int) -> str:
    return str(value)


@lru_cache(maxsize=1)
def _table():
    img = neon.wall(W, H, 0).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 120)))
    img.alpha_composite(neon.glow(neon.rounded_frame_mask((W, H), (12, 10, W - 12, H - 10), 28, 4), neon.CYAN, 5))
    return img


@lru_cache(maxsize=32)
def _face(value: int) -> Image.Image:
    color = COLORS[value - 1]
    card = Image.new("RGBA", (CW + 40, CH + 40), (0, 0, 0, 0))
    box = (20, 20, 20 + CW, 20 + CH)
    ImageDraw.Draw(card).rounded_rectangle(box, 18, fill=(20, 10, 26, 255))
    card.alpha_composite(neon.glow(neon.rounded_frame_mask(card.size, box, 18, 4), color, 5))
    icon = neon.icon_light(MONSTERS[value - 1], 84, color)
    card.alpha_composite(icon, ((card.width - icon.width) // 2, 30))
    card.alpha_composite(_neon_layer(card.size, label(value), (card.width // 2, 20 + CH - 52), 56, color, "mm"))
    d = ImageDraw.Draw(card)
    for x, y, a in ((34, 36, "la"), (card.width - 34, card.height - 36, "rd")):
        d.text((x, y), label(value), font=font("neon", 20), fill=(235, 225, 250), anchor=a)
    return card


@lru_cache(maxsize=1)
def _back() -> Image.Image:
    card = Image.new("RGBA", (CW + 40, CH + 40), (0, 0, 0, 0))
    box = (20, 20, 20 + CW, 20 + CH)
    ImageDraw.Draw(card).rounded_rectangle(box, 18, fill=(30, 10, 40, 255))
    card.alpha_composite(neon.glow(neon.rounded_frame_mask(card.size, box, 18, 4), neon.PURPLE, 5))
    inner = (36, 36, 4 + CW, 4 + CH)
    card.alpha_composite(neon.dim(neon.glow(neon.rounded_frame_mask(card.size, inner, 12, 2), neon.PINK, 3), 0.7))
    card.alpha_composite(_neon_layer(card.size, "?", (card.width // 2, card.height // 2), 90, neon.PINK, "mm"))
    return card


def _place(img, card, center, squash=1.0):
    if squash < 1:
        card = card.resize((max(2, round(card.width * squash)), card.height))
    img.alpha_composite(card, (round(center[0] - card.width / 2), round(center[1] - card.height / 2)))


def _scene(current, nxt=None, squash=1.0, streak=0, pot=0, verdict=None):
    img = _table().copy()
    _place(img, _face(current), LEFT)
    _place(img, _face(nxt) if nxt else _back(), RIGHT, squash)
    cx = 560
    img.alpha_composite(_neon_layer((W, H), "POT", (cx, 92), 22, neon.YELLOW, "mm"))
    img.alpha_composite(_neon_layer((W, H), f"{pot}", (cx, 132), 36 if pot < 10000 else 26, neon.YELLOW, "mm"))
    img.alpha_composite(_neon_layer((W, H), "SÉRIE", (cx, 196), 20, neon.CYAN, "mm"))
    img.alpha_composite(_neon_layer((W, H), f"{streak}", (cx, 232), 36, neon.CYAN, "mm"))
    if verdict:
        color = neon.GREEN if verdict in ("GAGNÉ", "ÉGALITÉ") else neon.RED
        img.alpha_composite(_neon_layer((W, H), verdict, (RIGHT[0], 34), 28, color, "mm"))
    return img


def table_png(current, streak, pot) -> bytes:
    return png_bytes(_scene(current, streak=streak, pot=pot).convert("RGB"))


def flip_gif(current, nxt, streak, pot, verdict) -> tuple[bytes, float]:
    frames, durations = [], []
    for k in range(6):  # back closes
        frames.append(_scene(current, None, 1 - k / 6, streak, pot))
        durations.append(45)
    for k in range(1, 7):  # face opens
        frames.append(_scene(current, nxt, k / 6, streak, pot))
        durations.append(45)
    frames.append(_scene(current, nxt, 1.0, streak, pot, verdict))
    durations.append(1600)
    return _gif_once(frames, durations), sum(durations) / 1000


def result_png(current, nxt, streak, pot, verdict) -> bytes:
    return png_bytes(_scene(current, nxt, 1.0, streak, pot, verdict).convert("RGB"))
