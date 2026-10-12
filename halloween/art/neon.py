"""Neon-sign toolkit: dark brick wall, glowing tubes, line-art icons, fog and sparks.

This is the visual signature of the bot: every banner and picture looks like
a haunted neon sign buzzing on an old brick wall.
"""
from __future__ import annotations

import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .canvas import font
from .emoji_art import EMOJIS, render_frame

ORANGE = (255, 122, 30)
PINK = (255, 60, 170)
CYAN = (60, 220, 255)
GREEN = (90, 255, 120)
PURPLE = (175, 95, 255)
RED = (255, 45, 70)
YELLOW = (255, 214, 60)
WHITE = (225, 235, 255)


@lru_cache(maxsize=16)
def wall(w: int, h: int, seed: int = 1, tint=(46, 26, 34)) -> Image.Image:
    """Old brick wall with mortar, grime and a dark vignette."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), (12, 8, 12))
    d = ImageDraw.Draw(img)
    bh, bw = 26, 70
    for row in range(h // bh + 2):
        off = (bw // 2) * (row % 2)
        for col in range(-1, w // bw + 2):
            x, y = col * bw + off, row * bh
            k = rnd.uniform(0.55, 1.0)
            c = tuple(int(v * k) for v in tint)
            d.rounded_rectangle((x + 2, y + 2, x + bw - 2, y + bh - 2), radius=3, fill=c)
            if rnd.random() < 0.18:  # chipped / darker brick
                d.rectangle((x + rnd.randint(4, 40), y + 4, x + rnd.randint(44, 66), y + bh - 6),
                            fill=tuple(int(v * 0.7) for v in c))
    img = img.filter(ImageFilter.GaussianBlur(0.7)).convert("RGBA")
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse((-w * 0.2, -h * 0.5, w * 1.2, h * 1.5), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(min(w, h) / 4))
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    shade.putalpha(ImageChops.invert(vig).point(lambda v: int(v * 0.85)))
    img.alpha_composite(shade)
    return img


def glow(mask: Image.Image, color, radius: float = 10, core=(255, 255, 255)) -> Image.Image:
    """Turn a tube mask (L) into a glowing neon light (RGBA)."""
    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    for r, strength in ((radius * 2.4, 0.5), (radius, 0.85), (radius * 0.35, 1.0)):
        g = mask.filter(ImageFilter.GaussianBlur(r)).point(lambda v, s=strength: min(255, int(v * 2.3 * s)))
        layer = Image.new("RGBA", mask.size, tuple(color) + (255,))
        layer.putalpha(g)
        out.alpha_composite(layer)
    # smooth the stair-steps of the drawn lines (ImageDraw does not antialias), keeping the tube bright
    smooth = mask.filter(ImageFilter.GaussianBlur(0.6)).point(lambda v: min(255, int(v * 1.35)))
    tube = Image.new("RGBA", mask.size, tuple(color) + (255,))
    tube.putalpha(smooth)
    out.alpha_composite(tube)
    inner = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.5))
    hot = tuple(int(a * 0.6 + b * 0.4) for a, b in zip(core, color))
    c = Image.new("RGBA", mask.size, hot + (255,))
    c.putalpha(inner)
    out.alpha_composite(c)
    return out


def text_mask(size_wh, text: str, size: int, xy, anchor="mm", fnt="neon") -> Image.Image:
    m = Image.new("L", size_wh, 0)
    ImageDraw.Draw(m).text(xy, text, font=font(fnt, size), fill=255, anchor=anchor)
    return m


def fit_text(text: str, size: int, max_w: int, fnt="neon") -> int:
    while size > 14 and font(fnt, size).getlength(text) > max_w:
        size -= 2
    return size


@lru_cache(maxsize=512)
def icon_mask(name: str, size: int, frame: int = 0) -> Image.Image:
    """Line art of one of our emojis: its dark outlines become neon tubes."""
    spec = EMOJIS[name]
    t = frame / spec.frames if spec.frames > 1 else 0.0
    im = render_frame(name, t, 128).resize((size, size), Image.LANCZOS)
    r, g, b, a = im.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    dark = lum.point(lambda v: 255 if v < 62 else 0)
    solid = a.point(lambda v: 255 if v > 120 else 0)
    dark = ImageChops.multiply(dark, solid)
    # keep thin strokes; big dark fills (hair, roofs…) are reduced to their outline
    k = max(5, (size // 18) | 1)
    blobs = dark.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    thin = ImageChops.subtract(dark, blobs)
    edge = ImageChops.subtract(blobs, blobs.filter(ImageFilter.MinFilter(5)))
    # plus the silhouette, so every creature keeps a closed outline
    rim = ImageChops.subtract(solid, solid.filter(ImageFilter.MinFilter(5)))
    lines = ImageChops.lighter(ImageChops.lighter(thin, edge), rim)
    return lines.filter(ImageFilter.GaussianBlur(0.5))


@lru_cache(maxsize=512)
def icon_light(name: str, size: int, color: tuple, frame: int = 0) -> Image.Image:
    """Glowing neon icon on a transparent canvas (with room for the glow)."""
    pad = size // 4
    m = Image.new("L", (size + pad * 2, size + pad * 2), 0)
    m.paste(icon_mask(name, size, frame), (pad, pad))
    return glow(m, color, max(4, size / 18))


def icon_frames(name: str) -> int:
    return EMOJIS[name].frames


def rounded_frame_mask(size_wh, box, radius=26, width=4) -> Image.Image:
    m = Image.new("L", size_wh, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, outline=255, width=width)
    return m


@lru_cache(maxsize=8)
def fog_strip(w: int, h: int, seed: int = 3) -> Image.Image:
    """Seamless (horizontally tileable) fog band, twice the banner width."""
    rnd = random.Random(seed)
    strip = Image.new("L", (w * 2, h), 0)
    d = ImageDraw.Draw(strip)
    for _ in range(26):
        x = rnd.uniform(0, w)
        y = rnd.uniform(h * 0.35, h * 1.05)
        rx, ry = rnd.uniform(60, 160), rnd.uniform(16, 34)
        v = rnd.randint(50, 120)
        for dx in (0, w):
            d.ellipse((x + dx - rx, y - ry, x + dx + rx, y + ry), fill=v)
    strip = strip.filter(ImageFilter.GaussianBlur(18))
    out = Image.new("RGBA", strip.size, (190, 170, 230, 255))
    out.putalpha(strip.point(lambda v: int(v * 0.55)))
    return out


def dim(img: Image.Image, factor: float) -> Image.Image:
    if factor >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * factor)))
    return out


# ---------------------------------------------------------------------------
# Neon emoji pack: every icon is a tiny glowing sign on a dark rounded tile.
# ---------------------------------------------------------------------------
EMOJI_COLORS = {
    ORANGE: ["pumpkin", "pumpkin_lit", "pumpkin_angry", "candy", "candy_bag", "fire", "cookie", "door", "hunter",
             "coffin", "lollipop"],
    CYAN: ["ghost", "ghost_still", "soul", "potion_blue", "hourglass", "eye", "moon", "tomb", "lock"],
    PURPLE: ["bat", "crystal", "spider", "web", "potion_purple", "book", "gem", "joker", "house", "reaper",
             "mummy", "feather", "question"],
    GREEN: ["witch", "zombie", "frog", "cauldron", "potion_green", "check", "mushroom"],
    RED: ["vampire", "demon", "heart", "cross", "potion_red", "fang", "werewolf"],
    YELLOW: ["trophy", "medal1", "crown", "chest", "star", "sparkle", "lightning", "key", "potion_gold", "wheel",
             "candle", "scroll"],
    PINK: ["gift", "dice", "shield", "skull_fire"],
    WHITE: ["skull", "bone", "medal2"],
}
_COLOR_OF = {name: color for color, names in EMOJI_COLORS.items() for name in names}
_COLOR_OF["medal3"] = (255, 150, 90)


def emoji_color(name: str):
    return _COLOR_OF.get(name, PURPLE)


def _bar_piece(part: str, on: bool) -> Image.Image:
    s = 128
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    x0 = 30 if part == "l" else -40
    x1 = 98 if part == "r" else 170
    d.rounded_rectangle((x0, 50, x1, 78), radius=14, outline=255, width=6)
    if on:
        fill = Image.new("L", (s, s), 0)
        ImageDraw.Draw(fill).rounded_rectangle((x0 + 8, 58, x1 - 8, 70), radius=6, fill=255)
        out.alpha_composite(glow(ImageChops.lighter(m, fill), ORANGE, 5))
    else:
        out.alpha_composite(dim(glow(m, (120, 90, 170), 3), 0.55))
    return out


def _details(name: str, m: Image.Image):
    """Details lost by the line extraction (filled shapes, digits)."""
    d = ImageDraw.Draw(m)
    if name == "dice":
        for x, y in ((44, 44), (84, 44), (64, 64), (44, 84), (84, 84)):
            d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=255)
    elif name.startswith("medal"):
        d.ellipse((44, 59, 84, 99), fill=0)
        d.text((64, 80), name[-1], font=font("neon", 32), fill=255, anchor="mm")


@lru_cache(maxsize=256)
def _silhouette(name: str, frame: int) -> Image.Image:
    """Filled shape of the icon (from the cartoon drawing), used as a soft coloured body."""
    spec = EMOJIS[name]
    t = frame / spec.frames if spec.frames > 1 else 0.0
    a = render_frame(name, t, 128).getchannel("A").resize((104, 104), Image.LANCZOS)
    return a.point(lambda v: 255 if v > 110 else 0).filter(ImageFilter.GaussianBlur(0.8))


@lru_cache(maxsize=16)
def _tile_base(color: tuple) -> Image.Image:
    """Glassy dark tile tinted with the icon colour: gradient, top gloss and a neon rim."""
    s = 128
    shape = Image.new("L", (s, s), 0)
    ImageDraw.Draw(shape).rounded_rectangle((2, 2, s - 3, s - 3), radius=30, fill=255)
    top = tuple(int(10 + c * 0.16) for c in color)
    grad = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(grad)
    for y in range(s):
        k = y / (s - 1)
        d.line((0, y, s, y), fill=(int(top[0] * (1 - k) + 9 * k), int(top[1] * (1 - k) + 5 * k),
                                    int(top[2] * (1 - k) + 14 * k), 255))
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(grad, (0, 0), shape)
    gloss = Image.new("L", (s, s), 0)
    ImageDraw.Draw(gloss).ellipse((-30, -70, s + 30, 46), fill=34)
    shine = Image.new("RGBA", (s, s), (255, 255, 255, 255))
    shine.putalpha(ImageChops.multiply(gloss.filter(ImageFilter.GaussianBlur(6)), shape))
    out.alpha_composite(shine)
    rim = Image.new("L", (s, s), 0)
    ImageDraw.Draw(rim).rounded_rectangle((4, 4, s - 5, s - 5), radius=28, outline=255, width=3)
    out.alpha_composite(dim(glow(rim, color, 2.5), 0.7))
    return out


def emoji_tile(name: str, frame: int = 0, flicker: float = 1.0) -> Image.Image:
    """128×128 RGBA neon emoji (one animation frame)."""
    if name.startswith("bar_"):
        return _bar_piece(name[4], name.endswith("1"))
    s = 128
    color = emoji_color(name)
    out = _tile_base(tuple(color)).copy()
    # soft coloured body so the shape reads even at 22 px
    body = Image.new("L", (s, s), 0)
    body.paste(_silhouette(name, frame), (12, 12))
    fill = Image.new("RGBA", (s, s), tuple(int(c * 0.55) for c in color) + (255,))
    fill.putalpha(body.point(lambda v: int(v * (0.42 + 0.12 * flicker))))
    out.alpha_composite(fill)
    lines = icon_mask(name, 104, frame).filter(ImageFilter.MaxFilter(5))
    m = Image.new("L", (s, s), 0)
    m.paste(lines, (12, 12))
    _details(name, m)
    out.alpha_composite(dim(glow(m, color, 3.2), flicker))
    # keep the tile's rounded corners clean after the glow
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((2, 2, s - 3, s - 3), radius=30, fill=255)
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out
