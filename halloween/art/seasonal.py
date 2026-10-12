"""Neon pictures for the October calendar and the giant pumpkin."""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import neon
from .canvas import font, png_bytes
from .cards import _neon_layer
from .emoji_art import emoji_image

W, H = 760, 500
COLS, FIRST_WEEKDAY = 7, 3  # 1 October 2026 is a Thursday
DAYS = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]


def _neon_text(img, text, xy, size, color, max_w=None):
    if max_w:
        size = neon.fit_text(text, size, max_w)
    img.alpha_composite(_neon_layer(img.size, text, tuple(xy), size, tuple(color), "mm"))


def calendar_png(opened: set[int], today: int | None, emojis: dict[int, str], first_weekday: int = FIRST_WEEKDAY) -> bytes:
    img = neon.wall(W, H, 6).copy()
    img.alpha_composite(Image.new("RGBA", (W, H), (6, 2, 12, 110)))
    _neon_text(img, "CALENDRIER D'OCTOBRE", (W / 2, 34), 34, neon.ORANGE)
    d = ImageDraw.Draw(img)
    cw, ch, x0, y0 = 100, 78, 30, 96
    for i, name in enumerate(DAYS):
        d.text((x0 + i * cw + cw / 2, 78), name, font=font("body", 15, "Bold"), fill=(200, 180, 230), anchor="mm")
    for day in range(1, 32):
        slot = first_weekday + day - 1
        col, row = slot % COLS, slot // COLS
        box = (x0 + col * cw + 5, y0 + row * ch + 5, x0 + (col + 1) * cw - 5, y0 + (row + 1) * ch - 5)
        is_open = day in opened
        is_today = day == today
        future = today is None or day > today
        fill = (28, 16, 38) if is_open else ((20, 12, 28) if not future else (12, 8, 16))
        d.rounded_rectangle(box, radius=14, fill=fill)
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(box, radius=14, outline=255, width=3)
        if is_today and not is_open:
            img.alpha_composite(neon.glow(m, neon.YELLOW, 6))
        elif is_open:
            img.alpha_composite(neon.dim(neon.glow(m, neon.GREEN, 3), 0.7))
        elif day == 31:
            img.alpha_composite(neon.dim(neon.glow(m, neon.RED, 4), 0.8))
        else:
            img.alpha_composite(neon.dim(neon.glow(m, neon.PURPLE, 3), 0.35 if future else 0.6))
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        if is_open:
            icon = emoji_image(emojis.get(day, "candy"), 44)
            img.alpha_composite(icon, (int(cx - 22), int(cy - 22)))
            d.text((box[0] + 10, box[1] + 8), str(day), font=font("body", 13, "Bold"), fill=(150, 255, 170))
        else:
            color = (255, 236, 150) if is_today else ((120, 100, 140) if future else (210, 190, 240))
            d.text((cx, cy), str(day), font=font("neon", 30), fill=color, anchor="mm")
    return png_bytes(img.convert("RGB"))


def giant_png(total: int, stage: int, stages: list, top: list[tuple[str, int]]) -> bytes:
    w, h = 760, 420
    img = neon.wall(w, h, 1).copy()
    img.alpha_composite(Image.new("RGBA", (w, h), (6, 2, 12, 90)))
    size = int(70 + 34 * stage)
    if stage == 0:
        art = neon.icon_light("mushroom", 70, neon.GREEN)
    else:
        art = neon.icon_light("pumpkin_lit" if stage >= 4 else "pumpkin", size, neon.ORANGE)
    _neon_text(img, "LA CITROUILLE GÉANTE", (230, 34), 30, neon.GREEN, max_w=400)
    ground = 380
    img.alpha_composite(art, (int(230 - art.width / 2), int(ground - art.height + art.height * 0.18)))
    d = ImageDraw.Draw(img)
    d.line((40, ground, 420, ground), fill=(90, 60, 50), width=4)
    name = stages[stage][1]
    _neon_text(img, name.upper(), (590, 70), 34, neon.ORANGE if stage < 6 else neon.RED, max_w=300)
    nxt = stages[stage + 1][0] if stage + 1 < len(stages) else None
    d.text((590, 120), f"{total:,} bonbons".replace(",", " "), font=font("body", 26, "Bold"), fill=(255, 240, 220),
           anchor="mm")
    x0, x1, y = 460, 720, 150
    d.rounded_rectangle((x0, y, x1, y + 22), radius=11, fill=(30, 20, 40))
    if nxt:
        base = stages[stage][0]
        frac = (total - base) / max(1, nxt - base)
        d.rounded_rectangle((x0, y, x0 + max(22, (x1 - x0) * min(1, frac)), y + 22), radius=11, fill=(255, 150, 40))
        d.text((590, y + 40), f"prochaine étape : {nxt:,}".replace(",", " "), font=font("body", 16, "SemiBold"),
               fill=(210, 190, 230), anchor="mm")
    else:
        d.rounded_rectangle((x0, y, x1, y + 22), radius=11, fill=(255, 60, 70))
        d.text((590, y + 40), "TAILLE MAXIMALE !", font=font("body", 16, "Bold"), fill=(255, 200, 200), anchor="mm")
    _neon_text(img, "JARDINIERS", (590, 236), 24, neon.GREEN)
    for i, (who, amount) in enumerate(top[:5]):
        d.text((470, 270 + i * 28), f"{i + 1}. {who[:16]}", font=font("body", 18, "SemiBold"), fill=(240, 230, 255),
               anchor="lm")
        d.text((720, 270 + i * 28), f"{amount:,}".replace(",", " "), font=font("body", 18, "Bold"),
               fill=(255, 190, 90), anchor="rm")
    return png_bytes(img.convert("RGB"))
