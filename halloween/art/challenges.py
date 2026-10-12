"""Neon board of the daily and weekly challenges."""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import neon
from .canvas import font, png_bytes
from .cards import _neon_layer
from .emoji_art import emoji_image

W = 760
ROW = 78


def _neon_text(img, text, xy, size, color, anchor="mm", max_w=None):
    if max_w:
        size = neon.fit_text(text, size, max_w)
    img.alpha_composite(_neon_layer(img.size, text, tuple(xy), size, tuple(color), anchor))


def _row(img, y, row):
    d = ImageDraw.Draw(img)
    box = (20, y, W - 20, y + ROW - 10)
    done = row["progress"] >= row["goal"]
    d.rounded_rectangle(box, radius=18, fill=(26, 14, 34) if not done else (20, 30, 26))
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=18, outline=255, width=3)
    if row["claimed"]:
        img.alpha_composite(neon.dim(neon.glow(m, neon.GREEN, 3), 0.55))
    elif done:
        img.alpha_composite(neon.glow(m, neon.YELLOW, 6))
    else:
        img.alpha_composite(neon.dim(neon.glow(m, neon.PURPLE, 3), 0.6))
    icon = emoji_image(row["icon"], 50)
    img.alpha_composite(icon, (34, y + (ROW - 10 - 50) // 2))
    text = row["text"]
    f = font("body", 19, "Bold")
    while f.getlength(text) > 470 and len(text) > 10:
        text = text[:-2].rstrip() + "…" if not text.endswith("…") else text[:-2] + "…"
    d.text((100, y + 20), text, font=f, fill=(245, 236, 255), anchor="lm")
    x0, x1, by = 100, 480, y + 46
    d.rounded_rectangle((x0, by, x1, by + 14), radius=7, fill=(40, 26, 52))
    ratio = max(0.0, min(1.0, row["progress"] / row["goal"]))
    if ratio > 0:
        bar = Image.new("L", img.size, 0)
        ImageDraw.Draw(bar).rounded_rectangle((x0, by, x0 + max(14, (x1 - x0) * ratio), by + 14), radius=7, fill=255)
        img.alpha_composite(neon.glow(bar, neon.GREEN if done else neon.CYAN, 3))
    d.text((x1 + 14, by + 7), f"{min(row['progress'], row['goal']):,}/{row['goal']:,}".replace(",", " "),
           font=font("body", 16, "Bold"), fill=(200, 190, 230), anchor="lm")
    if row["claimed"]:
        _neon_text(img, "RÉCUPÉRÉ", (680, y + (ROW - 10) / 2), 20, neon.GREEN)
    else:
        candy = emoji_image("candy", 30)
        img.alpha_composite(candy, (632, y + (ROW - 10) // 2 - 15))
        _neon_text(img, f"+{row['reward']}", (700, y + (ROW - 10) / 2), 24, neon.YELLOW if done else neon.ORANGE)


def board_png(daily: list[dict], weekly: list[dict], bonus_claimed: bool, bonus: int) -> bytes:
    h = 84 + len(daily) * ROW + 70 + len(weekly) * ROW + 14
    img = neon.wall(W, h, 4).copy()
    img.alpha_composite(Image.new("RGBA", (W, h), (6, 2, 12, 120)))
    _neon_text(img, "DÉFIS DU JOUR", (30, 42), 38, neon.PINK, anchor="lm")
    tag = "BONUS RÉCUPÉRÉ" if bonus_claimed else f"LES 3 = +{bonus} & 1 TICKET"
    _neon_text(img, tag, (W - 30, 44), 18, neon.GREEN if bonus_claimed else neon.YELLOW, anchor="rm")
    y = 84
    for row in daily:
        _row(img, y, row)
        y += ROW
    _neon_text(img, "DÉFIS DE LA SEMAINE", (30, y + 32), 30, neon.CYAN, anchor="lm")
    y += 70
    for row in weekly:
        _row(img, y, row)
        y += ROW
    return png_bytes(img.convert("RGB"))
