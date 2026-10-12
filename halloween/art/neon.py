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
    tube = Image.new("RGBA", mask.size, tuple(color) + (255,))
    tube.putalpha(mask)
    out.alpha_composite(tube)
    inner = mask.filter(ImageFilter.MinFilter(3))
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
