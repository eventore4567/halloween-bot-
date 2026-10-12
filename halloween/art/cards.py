"""Generated pictures: profile card, podium, wheel spin, collectible cards."""
from __future__ import annotations

import math
import random
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .canvas import Canvas, Grad, mix, png_bytes, rgba
from . import neon
from .emoji_art import emoji_image

INK = (24, 12, 32)
CREAM = (255, 246, 228)


def _safe_name(name: str, limit=18) -> str:
    """Fonts only cover Latin scripts; drop what would render as boxes."""
    keep = "".join(ch for ch in name if ord(ch) < 0x250 or ch in "’‘“”«»…–—")
    keep = keep.strip() or "Joueur"
    return keep if len(keep) <= limit else keep[: limit - 1] + "…"


def _avatar(data: bytes | None, size: int, ring=(255, 170, 60), ring2=(200, 80, 30)):
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = Canvas(size, size, ss=2)
    c.circle(size / 2, size / 2, size / 2 - 1, Grad(ring, ring2, "d"))
    c.circle(size / 2, size / 2, size / 2 - 7, INK)
    out = c.result()
    inner = size - 18
    try:
        img = Image.open(BytesIO(data)).convert("RGBA") if data else None
    except Exception:
        img = None
    if img is None:
        img = Image.new("RGBA", (inner, inner), (60, 40, 90, 255))
        ghost = emoji_image("ghost_still", int(inner * 0.7))
        img.alpha_composite(ghost, (int(inner * 0.15), int(inner * 0.15)))
    img = ImageOps.fit(img, (inner, inner), Image.LANCZOS)
    mask = Image.new("L", (inner * 4, inner * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, inner * 4 - 1, inner * 4 - 1), fill=255)
    mask = mask.resize((inner, inner), Image.LANCZOS)
    img.putalpha(mask)
    out.alpha_composite(img, (9, 9))
    return out


def _wall(c: Canvas, w, h, seed=3, frame=None):
    """Haunted brick wall background, optionally with a glowing neon frame."""
    c.paste(neon.wall(w, h, seed % 5), (0, 0), (w, h))
    if frame:
        c.paste(neon.glow(neon.rounded_frame_mask((w, h), (10, 10, w - 10, h - 10), 22, 4), frame, 6), (0, 0), (w, h))


@lru_cache(maxsize=128)
def _neon_layer(wh, text, xy, size, color, anchor):
    m = neon.text_mask(wh, text, size, xy, anchor)
    return neon.glow(m, color, max(3, size / 9))


def _neon_text(c: Canvas, text, xy, size, color, max_w=None, anchor="mm"):
    if max_w:
        size = neon.fit_text(text, size, max_w)
    c.paste(_neon_layer((c.w, c.h), text, tuple(xy), size, tuple(color), anchor), (0, 0), (c.w, c.h))


def _pill(c: Canvas, box, fill=(255, 255, 255, 26), outline=(255, 255, 255, 50)):
    c.rect(box, fill, outline, 2, radius=(box[3] - box[1]) / 2 if box[3] - box[1] < 60 else 18)


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------

def profile_card(name: str, title: str, level: int, xp: int, xp_need: int, candies: str, rank: str,
                 stats: list[tuple[str, str, str]], avatar: bytes | None, colors=((255, 150, 50), (120, 40, 10))) -> bytes:
    W, H = 900, 360
    c = Canvas(W, H, ss=2)
    _wall(c, W, H, seed=level, frame=colors[0])
    # soft glow behind the avatar
    c.circle(150, 165, 150, rgba(colors[0], 40))
    c.circle(150, 165, 118, rgba(colors[0], 50))
    av = _avatar(avatar, 220, colors[0], colors[1])
    c.paste(av, (40, 55))
    # level badge
    c.circle(232, 250, 34, Grad(colors[0], colors[1], "radial"), INK, 4)
    c.text((232, 240), "NIV.", "lilita", 13, CREAM)
    c.text((232, 260), str(level), "lilita", 28, CREAM, stroke=3, stroke_fill=INK)
    # name / title
    nm = _safe_name(name)
    size = 50
    while c.text_width(nm, "lilita", size) > 520 and size > 26:
        size -= 2
    c.text((300, 72), nm, "lilita", size, CREAM, anchor="lm", stroke=4, stroke_fill=INK)
    c.text((302, 116), title.upper(), "lilita", 20, rgba(colors[0]), anchor="lm", stroke=3, stroke_fill=INK)
    # xp bar
    bx, by, bw, bh = 300, 140, 560, 30
    c.rect((bx, by, bx + bw, by + bh), (20, 10, 30, 200), INK, 3, radius=15)
    ratio = 0 if xp_need <= 0 else max(0.0, min(1.0, xp / xp_need))
    if ratio > 0.02:
        c.rect((bx + 4, by + 4, bx + 4 + (bw - 8) * ratio, by + bh - 4), Grad(colors[0], colors[1], "h"), radius=11)
        c.rect((bx + 10, by + 7, bx + (bw - 8) * ratio - 4, by + 11), (255, 255, 255, 90), radius=2)
    c.text((bx + bw / 2, by + bh / 2 + 1), f"{xp} / {xp_need} XP", "lilita", 17, CREAM, stroke=3, stroke_fill=INK)
    # big stats
    big = [("candy", "BONBONS", candies), ("trophy", "CLASSEMENT", rank)]
    for i, (icon, label, value) in enumerate(big):
        x = 300 + i * 285
        _pill(c, (x, 186, x + 270, 250))
        c.paste(emoji_image(icon, 48), (x + 10, 194), (48, 48))
        c.text((x + 70, 204), label, "lilita", 14, (230, 220, 240), anchor="lm")
        vs = 26
        while c.text_width(value, "lilita", vs) > 190 and vs > 14:
            vs -= 1
        c.text((x + 70, 230), value, "lilita", vs, CREAM, anchor="lm", stroke=3, stroke_fill=INK)
    # small stats
    n = max(1, len(stats))
    sw = (560 - (n - 1) * 10) / n
    for i, (icon, label, value) in enumerate(stats):
        x = 300 + i * (sw + 10)
        _pill(c, (x, 262, x + sw, 318))
        c.paste(emoji_image(icon, 36), (x + 8, 272), (36, 36))
        c.text((x + 50, 279), label.upper(), "lilita", 11, (220, 210, 236), anchor="lm")
        c.text((x + 50, 301), value, "lilita", 19, CREAM, anchor="lm", stroke=2, stroke_fill=INK)
    img = c.result()
    return png_bytes(img)


# ---------------------------------------------------------------------------
# Podium
# ---------------------------------------------------------------------------

def podium(entries: list[tuple[str, str, bytes | None]], label: str) -> bytes:
    """entries: up to 3 (name, value, avatar bytes) in rank order."""
    W, H = 900, 400
    c = Canvas(W, H, ss=2)
    _wall(c, W, H, seed=7)
    spots = [(450, 150, 120, (255, 214, 90), (190, 110, 10), "medal1"),
             (240, 200, 100, (230, 236, 250), (130, 140, 170), "medal2"),
             (660, 220, 100, (255, 180, 120), (160, 80, 30), "medal3")]
    for i, (cx, top, w, col, col2, medal) in enumerate(spots):
        c.rect((cx - w, top + 80, cx + w, H + 10), Grad(mix(col, (60, 30, 90), 0.55), (30, 14, 50), "v"), INK, 4, radius=12)
    for i, (cx, top, w, col, col2, medal) in enumerate(spots):
        if i >= len(entries):
            c.text((cx, top + 30), "?", "title", 60, (255, 255, 255, 60))
            continue
        name, value, av = entries[i]
        size = 150 if i == 0 else 120
        if i == 0:
            c.paste(emoji_image("crown", 70), (cx - 35, top - 108), (70, 70))
        c.paste(_avatar(av, size, col, col2), (cx - size / 2, top - size / 2 - 22))
        c.paste(emoji_image(medal, 54), (cx + size / 2 - 40, top + size / 2 - 66), (54, 54))
        nm = _safe_name(name, 14)
        ns = 26
        while c.text_width(nm, "lilita", ns) > w * 2 - 16 and ns > 14:
            ns -= 1
        c.text((cx, top + 104), nm, "lilita", ns, CREAM, stroke=3, stroke_fill=INK)
        c.text((cx, top + 136), value, "lilita", 22, col, stroke=3, stroke_fill=INK)
    _neon_text(c, label.upper(), (W / 2, 30), 30, neon.YELLOW, max_w=W - 120)
    return png_bytes(c.result())


# ---------------------------------------------------------------------------
# Wheel of fortune
# ---------------------------------------------------------------------------

def _wheel_disc(segments, radius):
    size = radius * 2 + 20
    c = Canvas(size, size, ss=2)
    cx = cy = size / 2
    c.circle(cx, cy, radius + 8, Grad((255, 220, 120), (170, 100, 10), "d"), INK, 4)
    n = len(segments)
    for i, seg in enumerate(segments):
        start = -90 - 360 / n / 2 + i * 360 / n
        c.pie((cx - radius, cy - radius, cx + radius, cy + radius), start, start + 360 / n,
              Grad(mix(seg["color"], (255, 255, 255), 0.25), seg["color"], "radial"))
    for i in range(n):
        a = math.radians(-90 - 360 / n / 2 + i * 360 / n)
        c.line([(cx, cy), (cx + radius * math.cos(a), cy + radius * math.sin(a))], INK, 3)
    img = c.result()
    for i, seg in enumerate(segments):
        a = math.radians(-90 + i * 360 / n)
        r = radius * 0.66
        icon = emoji_image(seg["emoji"], 128).resize((54, 54), Image.LANCZOS)
        icon = icon.rotate(-(i * 360 / n), resample=Image.BICUBIC, expand=True)
        x = cx + r * math.cos(a) - icon.width / 2
        y = cy + r * math.sin(a) - icon.height / 2
        img.alpha_composite(icon, (int(x), int(y)))
    # rivets
    c2 = Canvas(size, size, ss=2)
    c2.img = img.resize((size * 2, size * 2), Image.LANCZOS)
    for i in range(n * 2):
        a = math.radians(i * 360 / (n * 2))
        c2.circle(cx + (radius + 4) * math.cos(a), cy + (radius + 4) * math.sin(a), 3.5, (255, 250, 220), INK, 1.5)
    c2.circle(cx, cy, 26, Grad((255, 230, 140), (200, 120, 20), "radial"), INK, 4)
    c2.circle(cx, cy, 9, INK)
    return c2.result()


@lru_cache(maxsize=16)
def wheel_gif(segments_key: tuple, target: int) -> bytes:
    from .. import config
    segments = config.WHEEL
    W, H = 640, 290
    radius = 118
    disc = _wheel_disc(segments, radius)
    base = Canvas(W, H, ss=2)
    _wall(base, W, H, seed=11)
    _neon_text(base, "ROUE DU DESTIN", (440, 60), 40, neon.YELLOW, max_w=340)
    bg = base.result()
    n = len(segments)
    final = -(target * 360 / n)
    turns = 3 * 360
    frames, durations = [], []
    steps = 24
    rnd = random.Random(target)
    wobble = rnd.uniform(-360 / n * 0.3, 360 / n * 0.3)
    for k in range(steps + 1):
        t = k / steps
        e = 1 - (1 - t) ** 3
        angle = final - (turns + wobble) * (1 - e)
        frame = bg.copy()
        rot = disc.rotate(-angle, resample=Image.BICUBIC)
        frame.alpha_composite(rot, (26, H // 2 - rot.height // 2))
        c = Canvas(W, H, ss=1)
        c.img = frame
        cx = 26 + rot.width / 2
        c.poly([(cx - 20, 6), (cx + 20, 6), (cx, 42)], (230, 60, 70), INK, 3)
        c.circle(cx, 12, 6, (255, 220, 120))
        if k == steps:
            seg = segments[target]
            _neon_text(c, "TU GAGNES", (440, 122), 28, neon.PINK)
            icon = emoji_image(seg["emoji"], 96)
            frame.alpha_composite(icon, (440 - 48, 140))
            label = seg["label"].upper()
            _neon_text(c, label, (440, 258), 38, neon.YELLOW, max_w=330)
        else:
            _neon_text(c, "La roue tourne…", (440, 170), 30, neon.CYAN)
        frames.append(frame)
        durations.append(60 if k < steps * 0.6 else 60 + int(140 * (k - steps * 0.6) / (steps * 0.4)))
    durations[-1] = 60000
    return _gif_once(frames, durations)


def _gif_once(frames, durations) -> bytes:
    frames = [f.convert("RGB") for f in frames]
    w, h = frames[0].size
    mosaic = Image.new("RGB", (w, h * 3))
    for i, f in enumerate((frames[0], frames[len(frames) // 2], frames[-1])):
        mosaic.paste(f, (0, h * i))
    pal = mosaic.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    buf = BytesIO()
    out[0].save(buf, format="GIF", save_all=True, append_images=out[1:], duration=durations, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Collectible cards
# ---------------------------------------------------------------------------
CW, CH = 300, 420


def card_face(card: dict, rarity: dict, number: int, total: int) -> Image.Image:
    c = Canvas(CW, CH, ss=2)
    col, col2 = rarity["color"], rarity["color2"]
    c.rect((4, 4, CW - 4, CH - 4), Grad(col, col2, "d"), INK, 5, radius=22)
    c.rect((16, 16, CW - 16, CH - 16), Grad((40, 22, 64), (16, 8, 28), "v"), mix(col, (255, 255, 255), 0.3), 3, radius=14)
    # art window
    c.rect((28, 58, CW - 28, 268), Grad(mix(col, (40, 20, 70), 0.55), (20, 10, 34), "radial"), INK, 3, radius=10)
    rnd = random.Random(card["key"])
    for _ in range(18):
        c.circle(rnd.uniform(36, CW - 36), rnd.uniform(66, 200), rnd.uniform(0.8, 2), (255, 250, 230, 160))
    c.circle(CW / 2, 168, 86, rgba(col, 60))
    art = neon.icon_light(card["emoji"], 150, tuple(col))
    c.paste(art, (CW / 2 - art.width / 2, 168 - art.height / 2), art.size)
    # name
    name = card["name"].upper()
    fs = 24
    while c.text_width(name, "lilita", fs) > CW - 50 and fs > 12:
        fs -= 1
    c.text((CW / 2, 36), name, "lilita", fs, CREAM, stroke=3, stroke_fill=INK)
    # stars
    s = rarity["stars"]
    for i in range(s):
        x = CW / 2 + (i - (s - 1) / 2) * 30
        c.star(x, 290, 13, 5.5, fill=Grad((255, 240, 150), (240, 160, 30), "radial"), outline=INK, width=2.5)
    c.text((CW / 2, 318), rarity["name"].upper(), "lilita", 16, rgba(col), stroke=2, stroke_fill=INK)
    # flavour text (wrapped)
    words, lines, cur = card["flavor"].split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if c.text_width(nxt, "body", 14) > CW - 60:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    lines.append(cur)
    for i, line in enumerate(lines[:3]):
        c.text((CW / 2, 346 + i * 18), line, "body", 14, (225, 215, 240))
    c.text((CW - 50, CH - 32), f"#{number:02d}/{total}", "lilita", 13, (200, 190, 220))
    return c.result()


def card_back() -> Image.Image:
    c = Canvas(CW, CH, ss=2)
    c.rect((4, 4, CW - 4, CH - 4), Grad((120, 70, 200), (40, 16, 80), "d"), INK, 5, radius=22)
    c.rect((18, 18, CW - 18, CH - 18), None, (255, 214, 100), 3, radius=14)
    for i in range(7):
        for j in range(10):
            if (i + j) % 2 == 0:
                c.circle(36 + i * 38, 40 + j * 38, 3, (255, 255, 255, 40))
    c.circle(CW / 2, CH / 2, 80, (30, 14, 50), (255, 214, 100), 4)
    c.paste(emoji_image("pumpkin_lit", 120), (CW / 2 - 60, CH / 2 - 62), (120, 120))
    c.text((CW / 2, CH - 50), "NUIT HANTÉE", "title", 26, (255, 214, 100), stroke=4, stroke_fill=INK)
    return c.result()


@lru_cache(maxsize=32)
def card_reveal_gif(card_key: str) -> bytes:
    from ..content.games import CARD, CARDS, RARITIES
    card = CARD[card_key]
    rarity = RARITIES[card["rarity"]]
    number = [c["key"] for c in CARDS].index(card_key) + 1
    face = card_face(card, rarity, number, len(CARDS))
    back = card_back()
    W, H = 520, 470
    base = Canvas(W, H, ss=1)
    _wall(base, W, H, seed=number)
    bg = base.result()
    glow_col = rarity["color"]
    frames, durations = [], []
    steps = 14
    for k in range(steps + 7):
        frame = bg.copy()
        if k <= steps:
            t = k / steps
            scale_x = abs(math.cos(t * math.pi))
            img = back if t < 0.5 else face
            bump = 1 + 0.08 * math.sin(t * math.pi)
        else:
            t = 1
            scale_x = 1
            img = face
            bump = 1
        w = max(2, int(CW * scale_x * bump))
        h = int(CH * bump)
        if t >= 0.5:
            # rarity glow, pulsing at the end
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gc = Canvas(W, H, ss=1)
            gc.img = g
            pulse = 1 if k <= steps else 1 + 0.06 * math.sin((k - steps) / 6 * math.tau)
            gc.circle(W / 2, H / 2, 210 * pulse, rgba(glow_col, 70))
            g = gc.img.filter(ImageFilter.GaussianBlur(26))
            frame.alpha_composite(g)
            if rarity["stars"] >= 3:
                rr = random.Random(k)
                for _ in range(10):
                    sc = Canvas(W, H, ss=1)
                    sc.img = frame
                    sc.sparkle(rr.uniform(30, W - 30), rr.uniform(20, H - 20), rr.uniform(4, 10), (255, 245, 200, 220))
        card_img = img.resize((w, h), Image.LANCZOS)
        frame.alpha_composite(card_img, ((W - w) // 2, (H - h) // 2))
        frames.append(frame)
        durations.append(70 if k <= steps else 110)
    durations[-1] = 60000
    return _gif_once(frames, durations)


def card_png(card_key: str) -> bytes:
    from ..content.games import CARD, CARDS, RARITIES
    card = CARD[card_key]
    number = [c["key"] for c in CARDS].index(card_key) + 1
    return png_bytes(card_face(card, RARITIES[card["rarity"]], number, len(CARDS)))
