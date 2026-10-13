"""La Chasse au trésor: the enigma pictures (cipher wheel, hidden parchment, word-search grid)."""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import png_bytes
from .cards import _neon_layer

W, H = 760, 420


@lru_cache(maxsize=2)
def _bg() -> Image.Image:
    img = neon.wall(W, H, 6).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (8, 4, 14, 170)))
    m = neon.rounded_frame_mask((W, H), (10, 8, W - 10, H - 8), 24, 4)
    img.alpha_composite(neon.glow(m, neon.YELLOW, 5))
    return img


def _text(img, text, xy, size, color, anchor="mm"):
    img.alpha_composite(_neon_layer((W, H), text, xy, size, tuple(color), anchor))


def _title(img, title, step):
    _text(img, f"ÉNIGME {step}/4", (W // 2, 34), 16, neon.PINK)
    _text(img, title, (W // 2, 64), neon.fit_text(title, 30, W - 80), neon.YELLOW)


def cipher_png(cipher_text: str, k: int) -> bytes:
    """A cipher wheel: outer alphabet, inner alphabet turned by ``k``, and the coded message."""
    img = _bg().copy()
    _title(img, "LE MESSAGE CHIFFRÉ", 1)
    cx, cy, r1, r2 = 200, 245, 140, 100
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((cx - r1 - 18, cy - r1 - 18, cx + r1 + 18, cy + r1 + 18), outline=255, width=3)
    d.ellipse((cx - r2 - 20, cy - r2 - 20, cx + r2 + 20, cy + r2 + 20), outline=255, width=2)
    d.ellipse((cx - r2 + 20, cy - r2 + 20, cx + r2 - 20, cy + r2 - 20), outline=255, width=3)
    img.alpha_composite(neon.glow(m, neon.PURPLE, 4))
    letters = Image.new("L", (W, H), 0)
    inner = Image.new("L", (W, H), 0)
    dl, di = ImageDraw.Draw(letters), ImageDraw.Draw(inner)
    font = neon.font("neon", 15)
    for i in range(26):
        a = -math.pi / 2 + i * math.tau / 26
        dl.text((cx + r1 * math.cos(a), cy + r1 * math.sin(a)), chr(65 + i), font=font, fill=255, anchor="mm")
        di.text((cx + r2 * math.cos(a), cy + r2 * math.sin(a)), chr(65 + (i + k) % 26), font=font,
                fill=255, anchor="mm")
    img.alpha_composite(neon.glow(letters, neon.CYAN, 2))
    img.alpha_composite(neon.glow(inner, neon.PINK, 2))
    arrow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(arrow).polygon([(cx - 8, cy - r1 - 34), (cx + 8, cy - r1 - 34), (cx, cy - r1 - 20)], fill=255)
    img.alpha_composite(neon.glow(arrow, neon.YELLOW, 3))
    _text(img, "A", (cx, cy), 40, neon.CYAN)
    _text(img, "MESSAGE INTERCEPTÉ :", (540, 160), 20, neon.WHITE)
    _text(img, cipher_text, (540, 214), neon.fit_text(cipher_text, 48, 380), neon.PINK)
    _text(img, "LA ROUE TRADUIT : CYAN → ROSE", (540, 280), 16, neon.PURPLE)
    _text(img, "À TOI DE FAIRE LE CHEMIN INVERSE…", (540, 310), 16, neon.PURPLE)
    return png_bytes(img.convert("RGB"))


def scroll_png(anagram: str) -> bytes:
    """The parchment hidden in another channel: the letters of the word, scrambled."""
    img = _bg().copy()
    _title(img, "LE PARCHEMIN CACHÉ", 2)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((90, 110, W - 90, 330), 18, outline=255, width=4)
    img.alpha_composite(neon.glow(m, neon.ORANGE, 5))
    n = len(anagram)
    size = min(64, (W - 220) // n)
    x0 = W // 2 - size * n / 2 + size / 2
    tiles = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(tiles)
    for i in range(n):
        x = x0 + i * size
        d.rounded_rectangle((x - size / 2 + 4, 186, x + size / 2 - 4, 186 + size), 8, outline=255, width=3)
    img.alpha_composite(neon.glow(tiles, neon.CYAN, 3))
    for i, c in enumerate(anagram):
        _text(img, c, (round(x0 + i * size), 186 + size // 2), int(size * 0.6), neon.YELLOW)
    _text(img, "LES LETTRES ONT ÉTÉ MÉLANGÉES PAR UN ESPRIT FARCEUR", (W // 2, 296), 16, neon.ORANGE)
    _text(img, "REMETS-LES DANS L'ORDRE : C'EST LA 2E RÉPONSE", (W // 2, 370), 18, neon.WHITE)
    return png_bytes(img.convert("RGB"))


def grid_png(lines: list[str], first: str, length: int) -> bytes:
    img = _bg().copy()
    _title(img, "LA GRILLE MAUDITE", 4)
    n = len(lines)
    cell = 30
    gx, gy = 70, 100
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((gx - 10, gy - 10, gx + cell * n + 10, gy + cell * n + 10), 12,
                                        outline=255, width=3)
    img.alpha_composite(neon.glow(m, neon.PURPLE, 4))
    letters = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(letters)
    font = neon.font("neon", 20)
    for y, row in enumerate(lines):
        for x, c in enumerate(row):
            d.text((gx + cell * x + cell / 2, gy + cell * y + cell / 2), c, font=font, fill=255, anchor="mm")
    img.alpha_composite(neon.glow(letters, neon.CYAN, 2))
    tx = 400 + (W - 400) // 2
    _text(img, "LE MOT FINAL SE CACHE ICI", (tx, 140), 20, neon.YELLOW)
    _text(img, f"{length} LETTRES", (tx, 200), 34, neon.PINK)
    _text(img, f"IL COMMENCE PAR « {first} »", (tx, 250), 22, neon.PINK)
    _text(img, "C'EST LA DERNIÈRE LETTRE", (tx, 300), 15, neon.PURPLE)
    _text(img, "DE LA 3E RÉPONSE", (tx, 322), 15, neon.PURPLE)
    _text(img, "→ ↓ ↘ ← ↑", (tx, 366), 20, neon.WHITE)
    return png_bytes(img.convert("RGB"))
