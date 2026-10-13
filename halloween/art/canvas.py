"""Tiny vector toolkit on top of Pillow.

Everything is drawn supersampled (``ss`` times larger) then reduced with a
Lanczos filter, which gives smooth anti-aliased shapes without any external
dependency. Coordinates are always expressed in *output* pixels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

Color = tuple


def rgba(color, alpha=None):
    """Accept '#rrggbb', (r, g, b) or (r, g, b, a)."""
    if isinstance(color, str):
        color = color.lstrip("#")
        color = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    if len(color) == 3:
        color = (*color, 255)
    if alpha is not None:
        color = (*color[:3], alpha)
    return tuple(int(c) for c in color)


def mix(a, b, t):
    a, b = rgba(a), rgba(b)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4))


@lru_cache(maxsize=64)
def font(name: str, size: int, weight: str | None = None):
    files = {
        "title": "LuckiestGuy-Regular.ttf",
        "lilita": "LilitaOne-Regular.ttf",
        "body": "Fredoka-Variable.ttf",
        "neon": "TiltNeon-Variable.ttf",
    }
    path = FONT_DIR / files.get(name, name)
    try:
        f = ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default(size)
    if name == "body":
        try:
            f.set_variation_by_name(weight or "SemiBold")
        except (OSError, ValueError):
            pass
    return f


@dataclass
class Grad:
    """Linear (vertical / horizontal / diagonal) or radial gradient."""
    a: Color
    b: Color
    kind: str = "v"  # v, h, d, radial
    center: tuple = (0.35, 0.3)  # radial highlight position inside the bbox

    def render(self, size):
        w, h = max(1, size[0]), max(1, size[1])
        if self.kind == "radial":
            base = Image.radial_gradient("L")  # 256x256, centre black
            # Move the bright spot to ``center`` by cropping an offset window.
            cx, cy = self.center
            scale = 2.0
            win = int(256 / scale)
            left = int(128 - win * cx)
            top = int(128 - win * cy)
            base = base.crop((left, top, left + win, top + win))
            mask = base.resize((w, h), Image.BILINEAR)
        else:
            base = Image.linear_gradient("L")
            if self.kind == "h":
                base = base.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
            elif self.kind == "d":
                base = base.rotate(45, resample=Image.BILINEAR, expand=True)
                o = base.width // 4
                base = base.crop((o, o, base.width - o, base.height - o))
            mask = base.resize((w, h), Image.BILINEAR)
        one = Image.new("RGBA", (w, h), rgba(self.a))
        two = Image.new("RGBA", (w, h), rgba(self.b))
        return Image.composite(two, one, mask)


class Canvas:
    def __init__(self, w, h, ss=4, bg=(0, 0, 0, 0)):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("RGBA", (w * ss, h * ss), rgba(bg))

    # -- geometry helpers -------------------------------------------------
    def _p(self, pts):
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    def _b(self, box):
        s = self.ss
        return [box[0] * s, box[1] * s, box[2] * s, box[3] * s]

    def _new_mask(self):
        return Image.new("L", self.img.size, 0)

    def paint(self, mask, fill):
        bbox = mask.getbbox()
        if not bbox:
            return
        m = mask.crop(bbox)
        if isinstance(fill, Grad):
            src = fill.render(m.size)
        elif isinstance(fill, Image.Image):
            src = fill.resize(m.size)
        else:
            src = Image.new("RGBA", m.size, rgba(fill))
        alpha = ImageChops.multiply(src.getchannel("A"), m)
        src.putalpha(alpha)
        self.img.alpha_composite(src, bbox[:2])

    def _shape(self, draw_fn, fill, outline, width):
        if fill is not None:
            m = self._new_mask()
            draw_fn(ImageDraw.Draw(m), 255, None, 0)
            self.paint(m, fill)
        if outline is not None and width:
            m = self._new_mask()
            draw_fn(ImageDraw.Draw(m), None, 255, max(1, round(width * self.ss)))
            self.paint(m, outline)

    # -- primitives ---------------------------------------------------------
    def ellipse(self, box, fill=None, outline=None, width=0):
        b = self._b(box)
        self._shape(lambda d, f, o, w: d.ellipse(b, fill=f, outline=o, width=w),
                    fill, outline, width)

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        self.ellipse((cx - r, cy - r, cx + r, cy + r), fill, outline, width)

    def rect(self, box, fill=None, outline=None, width=0, radius=0):
        b = self._b(box)
        r = radius * self.ss
        self._shape(lambda d, f, o, w: d.rounded_rectangle(b, radius=r, fill=f, outline=o, width=w),
                    fill, outline, width)

    def poly(self, pts, fill=None, outline=None, width=0):
        p = self._p(pts)

        def draw(d, f, o, w):
            if f is not None:
                d.polygon(p, fill=f)
            if o is not None:
                d.line(p + [p[0], p[1]], fill=o, width=w, joint="curve")
                for x, y in p:
                    d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=o)

        self._shape(draw, fill, outline, width)

    def line(self, pts, fill, width=3, cap=True):
        p = self._p(pts)
        w = max(1, round(width * self.ss))
        m = self._new_mask()
        d = ImageDraw.Draw(m)
        d.line(p, fill=255, width=w, joint="curve")
        if cap:
            for x, y in (p[0], p[-1]):
                d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=255)
        self.paint(m, fill)

    def arc(self, box, start, end, fill, width=3):
        b = self._b(box)
        m = self._new_mask()
        ImageDraw.Draw(m).arc(b, start, end, fill=255, width=max(1, round(width * self.ss)))
        self.paint(m, fill)

    def pie(self, box, start, end, fill=None, outline=None, width=0):
        b = self._b(box)
        self._shape(lambda d, f, o, w: d.pieslice(b, start, end, fill=f, outline=o, width=w),
                    fill, outline, width)

    def chord(self, box, start, end, fill=None, outline=None, width=0):
        b = self._b(box)
        self._shape(lambda d, f, o, w: d.chord(b, start, end, fill=f, outline=o, width=w),
                    fill, outline, width)

    def star(self, cx, cy, r_out, r_in, n=5, rot=-90, fill=None, outline=None, width=0):
        pts = []
        for i in range(n * 2):
            r = r_out if i % 2 == 0 else r_in
            a = math.radians(rot + i * 180 / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, fill, outline, width)

    def sparkle(self, cx, cy, r, fill, thin=0.22):
        k = r * thin
        self.poly([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
                   (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill)

    def text(self, xy, text, fnt_name, size, fill, anchor="mm", stroke=0, stroke_fill=None,
             weight=None, shadow=None):
        f = font(fnt_name, int(size * self.ss), weight)
        x, y = xy[0] * self.ss, xy[1] * self.ss
        if shadow:
            dx, dy, col = shadow
            m = self._new_mask()
            ImageDraw.Draw(m).text((x + dx * self.ss, y + dy * self.ss), text, font=f, fill=255,
                                   anchor=anchor, stroke_width=int(stroke * self.ss))
            self.paint(m, col)
        if stroke:
            m = self._new_mask()
            ImageDraw.Draw(m).text((x, y), text, font=f, fill=255, anchor=anchor,
                                   stroke_width=int(stroke * self.ss))
            self.paint(m, stroke_fill or (0, 0, 0))
        m = self._new_mask()
        ImageDraw.Draw(m).text((x, y), text, font=f, fill=255, anchor=anchor)
        self.paint(m, fill)

    def text_width(self, text, fnt_name, size, weight=None):
        f = font(fnt_name, int(size * self.ss), weight)
        return f.getlength(text) / self.ss

    def paste(self, image, xy, size=None):
        """Paste an RGBA image (output-pixel coordinates)."""
        size = size or image.size
        im = image.convert("RGBA").resize((int(size[0] * self.ss), int(size[1] * self.ss)), Image.LANCZOS)
        self.img.alpha_composite(im, (int(xy[0] * self.ss), int(xy[1] * self.ss)))

    def glow(self, color, radius, strength=1.0):
        """Soft glow behind everything drawn so far."""
        a = self.img.getchannel("A").filter(ImageFilter.GaussianBlur(radius * self.ss))
        if strength != 1.0:
            a = a.point(lambda v: min(255, int(v * strength)))
        layer = Image.new("RGBA", self.img.size, rgba(color))
        layer.putalpha(a)
        layer.alpha_composite(self.img)
        self.img = layer

    def outline(self, color=(28, 16, 38), width=3.0):
        """Sticker-style outline around the whole silhouette."""
        a = self.img.getchannel("A")
        r = width * self.ss
        grown = a.filter(ImageFilter.GaussianBlur(r * 0.55)).point(lambda v: 255 if v > 6 else 0)
        grown = grown.filter(ImageFilter.GaussianBlur(self.ss * 0.6))
        layer = Image.new("RGBA", self.img.size, rgba(color))
        layer.putalpha(grown)
        layer.alpha_composite(self.img)
        self.img = layer

    def shadow(self, dx=0, dy=3, blur=3, color=(0, 0, 0, 110)):
        a = self.img.getchannel("A").filter(ImageFilter.GaussianBlur(blur * self.ss))
        a = a.point(lambda v: v * rgba(color)[3] // 255)
        layer = Image.new("RGBA", self.img.size, rgba(color, 255))
        layer.putalpha(a)
        out = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        out.alpha_composite(layer, (int(dx * self.ss), int(dy * self.ss)))
        out.alpha_composite(self.img)
        self.img = out

    def result(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Encoders
# ---------------------------------------------------------------------------

def png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def gif_bytes(frames, duration=80, matte=(43, 45, 49), transparent=True, colors=255) -> bytes:
    """Encode RGBA frames as a looping GIF.

    GIF only has on/off transparency, so semi-transparent edge pixels are
    blended over ``matte`` (Discord's dark background) before quantising.
    """
    out = []
    for fr in frames:
        fr = fr.convert("RGBA")
        bg = Image.new("RGBA", fr.size, rgba(matte))
        bg.alpha_composite(fr)
        rgb = bg.convert("RGB")
        if transparent:
            q = rgb.quantize(colors=min(colors, 255), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            pal = q.getpalette()[: 255 * 3]
            pal += [0, 0, 0] * (256 - len(pal) // 3)
            q.putpalette(pal)
            hole = fr.getchannel("A").point(lambda v: 255 if v < 110 else 0)
            q.paste(255, mask=hole)
            q.info["transparency"] = 255
        else:
            q = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
        out.append(q)
    buf = BytesIO()
    kwargs = dict(save_all=True, append_images=out[1:], duration=duration, loop=0,
                  disposal=2, optimize=False)
    if transparent:
        kwargs["transparency"] = 255
    out[0].save(buf, format="GIF", **kwargs)
    return buf.getvalue()


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def best_palette(frames, colors: int = 255, sample: int = 16000, iters: int = 5, weight=None) -> Image.Image:
    """One palette for a whole animation, tuned for neon on a dark background.

    Pixels are sampled from frames spread over the whole clip (so colours that
    only show up for a moment still get a slot), bright pixels are over-sampled
    (glows and outlines matter more than the near-black sky), and a few k-means
    rounds move the median-cut colours to where the pixels really are.
    ``weight`` is an optional (x0, y0, x1, y1) box sampled twice as much.
    """
    rgb = [f.convert("RGB") for f in frames]
    step = max(1, len(rgb) // 24)
    picks = rgb[::step] + [rgb[-1]]
    chunks = [np.asarray(f.reduce(2)).reshape(-1, 3) for f in picks]
    if weight:
        chunks += [np.asarray(f.crop(weight).reduce(2)).reshape(-1, 3) for f in picks]
    px = np.concatenate(chunks).astype(np.float32)
    rng = np.random.default_rng(1)
    lum = px.max(1)
    bright, dark = px[lum > 50], px[lum <= 50]
    nb = min(len(bright), int(sample * 0.7))
    nd = min(len(dark), sample - nb)
    pts = np.concatenate([bright[rng.choice(len(bright), nb, replace=False)],
                          dark[rng.choice(len(dark), nd, replace=False)]])
    width = 200
    rows = max(1, len(pts) // width)
    seed_img = Image.fromarray(pts[:rows * width].reshape(rows, width, 3).astype(np.uint8), "RGB")
    seed = seed_img.quantize(colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    centers = np.array(seed.getpalette()[: colors * 3], dtype=np.float32).reshape(-1, 3)
    norms = (pts * pts).sum(1)[:, None]
    for _ in range(iters):
        nearest = (norms - 2 * pts @ centers.T + (centers * centers).sum(1)[None]).argmin(1)
        count = np.bincount(nearest, minlength=len(centers))
        for ch in range(3):
            total = np.bincount(nearest, weights=pts[:, ch], minlength=len(centers))
            centers[:, ch] = np.where(count > 0, total / np.maximum(count, 1), centers[:, ch])
    pal = Image.new("P", (1, 1))
    flat = np.clip(np.round(centers), 0, 255).astype(np.uint8).reshape(-1).tolist()
    pal.putpalette(flat + [0, 0, 0] * (256 - len(centers)))
    return pal


def encode_gif(frames, durations, loop: int | None = None, weight=None, **kwargs) -> bytes:
    """Opaque animated GIF with the shared :func:`best_palette` (no flicker, faithful neon)."""
    rgb = [f.convert("RGB") for f in frames]
    pal = best_palette(rgb, weight=weight)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb]
    buf = BytesIO()
    if loop is not None:
        kwargs["loop"] = loop
    out[0].save(buf, format="GIF", save_all=True, append_images=out[1:], duration=durations, optimize=True, **kwargs)
    return buf.getvalue()


def banner_gif_bytes(frames, duration=90) -> bytes:
    """Looping opaque GIF with one shared palette (no flicker).

    The running strip at the bottom (hero, monster) is small but moving: it is weighted more in the palette.
    """
    w, h = frames[0].size
    return encode_gif(frames, duration, loop=0, weight=(0, int(h * 0.7), w, h), disposal=1)
