"""« Le Grand Frisson » TV-show screens.

Each question is an animated GIF that plays once like a short video: the
neon studio, the money ladder, the question (or a creature hidden in the
shadows), the four answers and a countdown bar that drains to zero.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import neon
from .canvas import font, png_bytes
from .cards import _gif_once, _neon_layer
from .emoji_art import emoji_image, render_frame

W, H = 760, 430
MAIN_W = 590
LETTERS = "ABCD"
PILL_BOXES = [(24, 300, 300, 346), (310, 300, 586, 346), (24, 356, 300, 402), (310, 356, 586, 402)]
QBOX = (24, 64, 586, 286)
INK = (12, 6, 18)


def _wrap(text: str, size: int, max_w: int, fnt="body"):
    f = font(fnt, size, "SemiBold")
    words, lines, cur = text.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if f.getlength(nxt) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def _paste_neon_text(img, text, xy, size, color, max_w=None, anchor="mm"):
    if max_w:
        size = neon.fit_text(text, size, max_w)
    img.alpha_composite(_neon_layer((W, H), text, tuple(xy), size, tuple(color), anchor))


def _ladder(img, ladder, rung, safe):
    """Money ladder on the right; ``rung`` is the 0-based question being played."""
    d = ImageDraw.Draw(img)
    x0, x1, top, step = 604, 744, 24, 33
    for i in range(len(ladder) - 1, -1, -1):
        y = top + (len(ladder) - 1 - i) * step
        current = i == rung
        done = i < rung
        if current:
            glow = Image.new("L", (W, H), 0)
            ImageDraw.Draw(glow).rounded_rectangle((x0, y, x1, y + step - 5), radius=10, outline=255, width=3)
            img.alpha_composite(neon.glow(glow, neon.ORANGE, 5))
        color = (255, 214, 60) if (i + 1) in safe else ((255, 255, 255) if current else
                                                         (150, 140, 175) if done else (205, 195, 225))
        f = font("body", 17, "Bold")
        d.text((x0 + 12, y + 14), f"{i + 1}", font=f, fill=(120, 110, 150) if not current else (255, 200, 120),
               anchor="lm")
        d.text((x1 - 34, y + 14), f"{ladder[i]}", font=f, fill=color, anchor="rm")
        img.alpha_composite(emoji_image("candy", 22), (x1 - 30, y + 3))


def _pills(img, options, removed=(), good=None, bad=None):
    d = ImageDraw.Draw(img)
    for i, (box, opt) in enumerate(zip(PILL_BOXES, options)):
        x0, y0, x1, y1 = box
        if i in removed:
            d.rounded_rectangle(box, radius=23, fill=(20, 14, 26), outline=(50, 40, 60), width=2)
            continue
        color = neon.PURPLE
        fill = (26, 16, 40)
        if good == i:
            color, fill = neon.GREEN, (20, 70, 36)
        elif bad == i:
            color, fill = neon.RED, (80, 16, 26)
        d.rounded_rectangle(box, radius=23, fill=fill)
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(box, radius=23, outline=255, width=3)
        img.alpha_composite(neon.glow(m, color, 4))
        d.text((x0 + 26, (y0 + y1) / 2), LETTERS[i], font=font("neon", 26), fill=(255, 170, 70), anchor="mm")
        size = 19
        f = font("body", size, "SemiBold")
        while f.getlength(opt) > (x1 - x0 - 62) and size > 12:
            size -= 1
            f = font("body", size, "SemiBold")
        d.text((x0 + 46, (y0 + y1) / 2), opt, font=f, fill=(245, 240, 255), anchor="lm")


def _studio(rung, ladder, safe, value):
    img = neon.wall(W, H, 4).copy()
    shade = Image.new("RGBA", (W, H), (6, 2, 12, 120))
    img.alpha_composite(shade)
    _paste_neon_text(img, "LE GRAND FRISSON", (190, 32), 30, neon.PINK)
    img.alpha_composite(emoji_image("skull", 40), (18, 12))
    _paste_neon_text(img, f"QUESTION {rung + 1} · {value}", (470, 32), 24, neon.YELLOW, max_w=220)
    _ladder(img, ladder, rung, safe)
    return img


def _question_box(img, color=neon.CYAN):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(QBOX, radius=20, fill=(10, 8, 20, 230))
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle(QBOX, radius=20, outline=255, width=3)
    img.alpha_composite(neon.glow(m, color, 5))


def _question_text(img, text, category):
    d = ImageDraw.Draw(img)
    d.text(((QBOX[0] + QBOX[2]) / 2, QBOX[1] + 22), category.upper(), font=font("body", 15, "Bold"),
           fill=(150, 220, 255), anchor="mm")
    size = 28
    while True:
        lines = _wrap(text, size, QBOX[2] - QBOX[0] - 50)
        if len(lines) <= 5 or size <= 16:
            break
        size -= 2
    lh = size * 1.25
    y = (QBOX[1] + QBOX[3]) / 2 + 10 - lh * (len(lines) - 1) / 2
    f = font("body", size, "SemiBold")
    for line in lines[:6]:
        d.text(((QBOX[0] + QBOX[2]) / 2, y), line, font=f, fill=(255, 255, 255), anchor="mm")
        y += lh


def _silhouette(name: str, phase: str, size=170):
    """phase: 'shadow' (black shape) or 'neon' (outline revealed)."""
    if phase == "neon":
        return neon.icon_light(name, size, neon.GREEN)
    im = render_frame(name, 0.0, 128).resize((size, size), Image.LANCZOS)
    a = im.getchannel("A")
    shape = Image.new("RGBA", im.size, (4, 2, 8, 255))
    shape.putalpha(a)
    rim = ImageChops.subtract(a, a.filter(ImageFilter.MinFilter(5)))
    pad = size // 4
    out = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    m = Image.new("L", out.size, 0)
    m.paste(rim, (pad, pad))
    out.alpha_composite(neon.glow(m, neon.PURPLE, 6))
    out.alpha_composite(shape, (pad, pad))
    return out


def _bar(img, frac, seconds_left):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 24, 408, 586, 426
    d.rounded_rectangle((x0, y0, x1, y1), radius=9, fill=(30, 22, 40))
    if frac > 0:
        col = (90, 255, 120) if frac > 0.5 else ((255, 190, 50) if frac > 0.2 else (255, 60, 70))
        d.rounded_rectangle((x0, y0, max(x0 + 18, x0 + (x1 - x0) * frac), y1), radius=9, fill=col)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), f"{seconds_left} s", font=font("body", 15, "Bold"),
           fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(20, 10, 30))


def question_gif(text: str, category: str, options: list[str], rung: int, ladder: list[int], safe: set,
                 seconds: int, removed=(), shadow: str | None = None) -> bytes:
    base = _studio(rung, ladder, safe, ladder[rung])
    _question_box(base, neon.GREEN if shadow else neon.CYAN)
    _pills(base, options, removed)
    if shadow:
        d = ImageDraw.Draw(base)
        d.text(((QBOX[0] + QBOX[2]) / 2, QBOX[1] + 22), "QUI SE CACHE DANS L'OMBRE ?",
               font=font("body", 16, "Bold"), fill=(170, 255, 190), anchor="mm")
    frames, durations = [], []
    for s in range(seconds + 1):
        img = base.copy()
        if shadow:
            phase = "shadow" if s < seconds * 0.55 else "neon"
            sil = _silhouette(shadow, phase)
            img.alpha_composite(sil, (int((QBOX[0] + QBOX[2]) / 2 - sil.width / 2),
                                      int((QBOX[1] + QBOX[3]) / 2 + 12 - sil.height / 2)))
        else:
            _question_text(img, text, category)
        left = seconds - s
        _bar(img, left / seconds, left)
        if left == 0:
            _paste_neon_text(img, "TEMPS ÉCOULÉ !", (305, 175), 46, neon.RED)
        frames.append(img)
        durations.append(1000)
    durations[-1] = 60000
    return _gif_once(frames, durations)


def reveal_png(text: str, category: str, options: list[str], rung: int, ladder: list[int], safe: set,
               correct: int, picked: int | None, removed=(), shadow: str | None = None, banner: str = "") -> bytes:
    img = _studio(rung, ladder, safe, ladder[rung])
    ok = picked == correct
    _question_box(img, neon.GREEN if ok else neon.RED)
    if shadow:
        img.alpha_composite(emoji_image(shadow, 150), (int((QBOX[0] + QBOX[2]) / 2 - 75), QBOX[1] + 40))
    else:
        _question_text(img, text, category)
    _pills(img, options, removed, good=correct, bad=None if ok else picked)
    if banner:
        _paste_neon_text(img, banner, ((QBOX[0] + QBOX[2]) / 2, QBOX[3] - 26), 28, neon.GREEN if ok else neon.RED,
                         max_w=540)
    return png_bytes(img.convert("RGB"))


def first_frame(data: bytes) -> Image.Image:
    im = Image.open(BytesIO(data))
    return im.convert("RGB")
