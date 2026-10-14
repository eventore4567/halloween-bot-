"""Profile picture and banner of the bot for the ODB Discord server.

    python -m tools.brand_art

Writes assets/brand/avatar.png (1024x1024, cropped to a circle by Discord)
and assets/brand/banner.png (1500x600, the 5:2 ratio of Discord profile banners).
The ODB monogram is two silver back-to-back D's, lit like the bot's neon signs.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from halloween.art.neon import (CYAN, ORANGE, PINK, PURPLE, fog_strip, glow, icon_light, rounded_frame_mask,
                                text_mask, wall)

OUT = Path(__file__).resolve().parent.parent / "assets" / "brand"
SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"


def _d_mask(h: int) -> Image.Image:
    """One serif 'D' cropped to its ink, `h` pixels tall."""
    try:
        f = ImageFont.truetype(SERIF, h * 2)
    except OSError:
        f = ImageFont.load_default(h * 2)
    m = Image.new("L", (h * 3, h * 3), 0)
    ImageDraw.Draw(m).text((h // 2, h // 2), "D", font=f, fill=255)
    m = m.crop(m.getbbox())
    return m.resize((round(m.width * h / m.height), h), Image.LANCZOS)


def monogram_mask(h: int, gap: float = 0.04) -> Image.Image:
    """Mirrored D + D with their stems side by side, like the ODB logo."""
    d = _d_mask(h)
    g = max(2, round(h * gap))
    m = Image.new("L", (d.width * 2 + g, h), 0)
    m.paste(ImageOps.mirror(d), (0, 0))
    m.paste(d, (d.width + g, 0))
    return m


def silver(mask: Image.Image) -> Image.Image:
    """Brushed-metal fill: bright top, dark band, bright rim at the bottom."""
    w, h = mask.size
    grad = Image.new("RGB", (1, h))
    stops = [(0.0, (250, 250, 252)), (0.42, (178, 180, 188)), (0.55, (92, 94, 104)),
             (0.75, (196, 198, 206)), (1.0, (130, 132, 140))]
    for y in range(h):
        t = y / max(1, h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                grad.putpixel((0, y), tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    metal = grad.resize((w, h)).convert("RGBA")
    # thin dark bevel so the letters read on the glow
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(5)))
    shade = Image.new("RGBA", (w, h), (30, 20, 30, 255))
    shade.putalpha(edge.point(lambda v: int(v * 0.6)))
    metal.alpha_composite(shade)
    metal.putalpha(mask)
    return metal


def monogram(h: int, halo=ORANGE, pad: int | None = None) -> Image.Image:
    """Silver monogram with a neon halo, on a transparent canvas."""
    pad = pad if pad is not None else h // 2
    m = monogram_mask(h)
    big = Image.new("L", (m.width + pad * 2, m.height + pad * 2), 0)
    big.paste(m, (pad, pad))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    # soft halo around the letters, then a neon tube hugging their outline
    soft = big.filter(ImageFilter.GaussianBlur(h / 6)).point(lambda v: min(255, int(v * 0.9)))
    layer = Image.new("RGBA", big.size, tuple(halo) + (255,))
    layer.putalpha(soft)
    out.alpha_composite(layer)
    rim = ImageChops.subtract(big.filter(ImageFilter.MaxFilter(max(3, (h // 40) | 1))), big)
    out.alpha_composite(glow(rim, halo, max(3, h / 40)))
    plate = Image.new("RGBA", big.size, (10, 5, 14, 255))
    plate.putalpha(ImageChops.subtract(big.filter(ImageFilter.MaxFilter(3)), big))
    out.alpha_composite(plate)
    out.alpha_composite(silver(big))
    return out


def _paste_c(dst: Image.Image, src: Image.Image, cx: float, cy: float):
    dst.alpha_composite(src, (round(cx - src.width / 2), round(cy - src.height / 2)))


def _bat_mask(w: int) -> Image.Image:
    """Solid bat silhouette, `w` pixels wide."""
    s = 4
    W, H = w * s, int(w * 0.5) * s
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    cx, cy = W / 2, H * 0.42
    pts = [(cx, cy - H * 0.12), (cx + W * 0.08, cy - H * 0.3), (cx + W * 0.1, cy - H * 0.06),
           (cx + W * 0.28, cy - H * 0.4), (cx + W * 0.5, cy - H * 0.2), (cx + W * 0.42, cy + H * 0.12),
           (cx + W * 0.33, cy + H * 0.02), (cx + W * 0.24, cy + H * 0.3), (cx + W * 0.14, cy + H * 0.12),
           (cx + W * 0.06, cy + H * 0.36), (cx, cy + H * 0.2)]
    pts += [(2 * cx - x, y) for x, y in reversed(pts[1:-1])]
    d.polygon(pts, fill=255)
    d.ellipse((cx - W * 0.06, cy - H * 0.18, cx + W * 0.06, cy + H * 0.3), fill=255)
    return m.resize((w, int(w * 0.5)), Image.LANCZOS)


def _bats(img: Image.Image, spots, color=(8, 4, 10)):
    for x, y, w, rot in spots:
        bm = _bat_mask(w).rotate(rot, expand=True, resample=Image.BICUBIC)
        rim = glow(ImageChops.subtract(bm, bm.filter(ImageFilter.MinFilter(3))), PURPLE, max(2, w / 30))
        body = Image.new("RGBA", bm.size, color + (255,))
        body.putalpha(bm)
        _paste_c(img, rim, x, y)
        _paste_c(img, body, x, y)


def _moon(r: int, color=(255, 214, 140)) -> Image.Image:
    size = r * 4
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((r, r, r * 3, r * 3), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    halo = Image.new("RGBA", (size, size), color + (255,))
    halo.putalpha(m.filter(ImageFilter.GaussianBlur(r * 0.45)).point(lambda v: int(v * 0.55)))
    out.alpha_composite(halo)
    disc = Image.new("RGBA", (size, size), color + (255,))
    disc.putalpha(m)
    out.alpha_composite(disc)
    rnd = random.Random(4)
    craters = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(craters)
    for _ in range(9):
        a, k = rnd.uniform(0, math.tau), rnd.uniform(0, 0.7) * r
        cr = rnd.uniform(0.08, 0.2) * r
        x, y = 2 * r + math.cos(a) * k, 2 * r + math.sin(a) * k
        d.ellipse((x - cr, y - cr, x + cr, y + cr), fill=70)
    craters = ImageChops.multiply(craters.filter(ImageFilter.GaussianBlur(r * 0.03)), m)
    shade = Image.new("RGBA", (size, size), (190, 120, 60, 255))
    shade.putalpha(craters)
    out.alpha_composite(shade)
    return out


def _sky(w: int, h: int, top=(14, 6, 26), bottom=(58, 18, 30)) -> Image.Image:
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = (y / h) ** 1.4
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    img = col.resize((w, h)).convert("RGBA")
    rnd = random.Random(7)
    d = ImageDraw.Draw(img)
    for _ in range(w * h // 5000):
        x, y, v = rnd.uniform(0, w), rnd.uniform(0, h * 0.75), rnd.randint(110, 230)
        rr = rnd.choice((1, 1, 1, 2))
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(v, v, min(255, v + 20), 255))
    return img


def _ring(size: int, r: float, width: int, color) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    c = size / 2
    ImageDraw.Draw(m).ellipse((c - r, c - r, c + r, c + r), outline=255, width=width)
    return glow(m, color, width * 1.6)


def _hat(w: int) -> Image.Image:
    """Witch hat (black felt, neon purple rim, orange band)."""
    s = 4
    W, H = w * s, w * s
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    brim_y = H * 0.78
    d.ellipse((0, brim_y - H * 0.09, W, brim_y + H * 0.09), fill=255)
    d.polygon([(W * 0.2, brim_y), (W * 0.8, brim_y), (W * 0.62, H * 0.35), (W * 0.78, H * 0.04),
               (W * 0.48, H * 0.3), (W * 0.36, H * 0.55)], fill=255)
    m = m.resize((w, w), Image.LANCZOS)
    band = Image.new("L", (W, H), 0)
    ImageDraw.Draw(band).polygon([(W * 0.22, brim_y - H * 0.02), (W * 0.78, brim_y - H * 0.02),
                                  (W * 0.74, brim_y - H * 0.13), (W * 0.26, brim_y - H * 0.13)], fill=255)
    band = ImageChops.multiply(band.resize((w, w), Image.LANCZOS), m)
    out = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    out.alpha_composite(glow(ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(5))), PURPLE, w / 60))
    felt = Image.new("RGBA", (w, w), (16, 8, 22, 255))
    felt.putalpha(m)
    out.alpha_composite(felt)
    band_fill = Image.new("RGBA", (w, w), ORANGE + (255,))
    band_fill.putalpha(band)
    out.alpha_composite(band_fill)
    return out


def avatar(size: int = 1024) -> Image.Image:
    img = _sky(size, size)
    c = size / 2
    # purple haze behind the monogram
    haze = Image.new("L", (size, size), 0)
    rr = size * 0.3
    ImageDraw.Draw(haze).ellipse((c - rr, c - rr * 0.8, c + rr, c + rr * 0.8), fill=150)
    layer = Image.new("RGBA", (size, size), (110, 40, 150, 255))
    layer.putalpha(haze.filter(ImageFilter.GaussianBlur(size * 0.09)))
    img.alpha_composite(layer)
    _paste_c(img, _moon(int(size * 0.085)), size * 0.3, size * 0.25)

    img.alpha_composite(_ring(size, size * 0.465, max(6, size // 110), ORANGE))
    img.alpha_composite(_ring(size, size * 0.43, max(3, size // 260), PURPLE))

    hill = Image.new("L", (size, size), 0)
    ImageDraw.Draw(hill).ellipse((-size * 0.2, size * 0.8, size * 1.2, size * 1.5), fill=255)
    ground = Image.new("RGBA", (size, size), (6, 3, 8, 255))
    ground.putalpha(hill)
    img.alpha_composite(ground)

    mh = int(size * 0.26)
    _paste_c(img, monogram(mh), c, size * 0.53)
    hat = _hat(int(size * 0.32))
    _paste_c(img, hat, c + size * 0.1, size * 0.53 - mh / 2 - hat.height * 0.36)
    _bats(img, [(size * 0.8, size * 0.28, int(size * 0.12), -12), (size * 0.2, size * 0.43, int(size * 0.08), 10),
                (size * 0.47, size * 0.17, int(size * 0.07), -4)])
    _paste_c(img, icon_light("pumpkin_lit", int(size * 0.2), ORANGE), size * 0.29, size * 0.8)
    _paste_c(img, icon_light("ghost", int(size * 0.17), CYAN), size * 0.72, size * 0.79)
    return img.convert("RGB")


def banner(w: int = 1500, h: int = 600) -> Image.Image:
    img = wall(w, h, seed=11).copy()
    _paste_c(img, _moon(int(h * 0.1)), w * 0.9, h * 0.25)

    frame = rounded_frame_mask((w, h), (40, 40, w - 40, h - 40), radius=46, width=7)
    img.alpha_composite(glow(frame, PINK, 9))

    # Discord puts the avatar over the bottom-left corner: keep the monogram above it
    mh, mx, my = int(h * 0.3), w * 0.2, h * 0.47
    _paste_c(img, monogram(mh, pad=int(h * 0.14)), mx, my)
    hat = _hat(int(h * 0.34))
    _paste_c(img, hat, mx + mh * 0.38, my - mh / 2 - hat.height * 0.36)

    tx = w * 0.62
    img.alpha_composite(glow(text_mask((w, h), "NUIT HANTÉE", 132, (tx, h * 0.4)), ORANGE, 10))
    img.alpha_composite(glow(text_mask((w, h), "LE BOT HALLOWEEN D'ODB", 52, (tx, h * 0.62)), PURPLE, 6))

    _bats(img, [(w * 0.4, h * 0.2, 90, 10), (w * 0.78, h * 0.15, 70, -12), (w * 0.52, h * 0.84, 60, 6)])
    _paste_c(img, icon_light("pumpkin_lit", 120, ORANGE), w * 0.42, h * 0.8)
    _paste_c(img, icon_light("ghost", 110, CYAN), w * 0.87, h * 0.77)
    _paste_c(img, icon_light("candy", 80, ORANGE), w * 0.68, h * 0.82)

    fog = fog_strip(w, h // 2, seed=5).crop((0, 0, w, h // 2))
    img.alpha_composite(fog, (0, h - h // 2))
    return img.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    avatar().save(OUT / "avatar.png", optimize=True)
    banner().save(OUT / "banner.png", optimize=True)
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
