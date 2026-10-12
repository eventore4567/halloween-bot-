"""2D side-scrolling engine: a haunted world in parallax and a running pumpkin hero.

Used for the end-of-game cutscenes (the hero runs, meets the game's monster,
then wins candies or gets knocked out) and for the running strip of the banners.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from . import neon
from .cards import _neon_layer

W, H = 680, 300
GROUND = 246


# --------------------------------------------------------------------------- world layers
@lru_cache(maxsize=4)
def sky(w: int = W, h: int = H) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        d.line((0, y, w, y), fill=(int(28 - 18 * k), int(10 - 6 * k), int(48 - 30 * k), 255))
    rnd = random.Random(7)
    for _ in range(70):
        x, y = rnd.randrange(w), rnd.randrange(int(h * 0.6))
        v = rnd.randrange(120, 255)
        d.point((x, y), fill=(v, v, min(255, v + 30), 255))
    moon = Image.new("L", (w, h), 0)
    ImageDraw.Draw(moon).ellipse((w - 150, 22, w - 80, 92), fill=255)
    img.alpha_composite(neon.glow(moon, (255, 236, 170), 10))
    return img


@lru_cache(maxsize=8)
def hills(period: int = 340, h: int = H, ground: int = GROUND) -> Image.Image:
    """Far hills: dark silhouette with a thin neon edge, tiles horizontally every ``period``."""
    w = period * 3
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pts = [(x, ground - 60 - 34 * math.sin(x / period * math.tau) - 14 * math.sin(x / period * math.tau * 3))
           for x in range(0, w + 1, 4)]
    d = ImageDraw.Draw(img)
    d.polygon(pts + [(w, h), (0, h)], fill=(22, 10, 34, 255))
    edge = Image.new("L", (w, h), 0)
    ImageDraw.Draw(edge).line(pts, fill=255, width=2)
    img.alpha_composite(neon.dim(neon.glow(edge, neon.PURPLE, 3), 0.55))
    return img


@lru_cache(maxsize=8)
def graveyard(period: int = 190, h: int = H, ground: int = GROUND, seed: int = 3) -> Image.Image:
    """Middle layer: tombstones, crosses and dead trees, repeating every ``period``."""
    w = period * 4
    rnd = random.Random(seed)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for k in range(4):
        x0 = k * period + rnd.randint(10, 40)
        kind = k % 3
        if kind == 0:  # tombstone
            d.rounded_rectangle((x0, ground - 46, x0 + 30, ground), 12, outline=255, width=3)
            d.line((x0 + 9, ground - 30, x0 + 21, ground - 30), fill=255, width=2)
        elif kind == 1:  # cross
            d.line((x0 + 14, ground - 56, x0 + 14, ground), fill=255, width=3)
            d.line((x0, ground - 42, x0 + 28, ground - 42), fill=255, width=3)
        else:  # dead tree
            d.line((x0 + 20, ground, x0 + 20, ground - 84), fill=255, width=4)
            d.line((x0 + 20, ground - 56, x0 + 44, ground - 80), fill=255, width=3)
            d.line((x0 + 20, ground - 66, x0 - 2, ground - 92), fill=255, width=3)
            d.line((x0 + 34, ground - 70, x0 + 46, ground - 66), fill=255, width=2)
        x1 = k * period + period - 50
        d.line((x1, ground - 22, x1 + 40, ground - 22), fill=255, width=2)  # little fence
        for fx in range(x1, x1 + 41, 10):
            d.line((fx, ground - 30, fx, ground), fill=255, width=2)
    return neon.dim(neon.glow(m, neon.GREEN, 3), 0.75)


@lru_cache(maxsize=8)
def ground_strip(period: int = 48, w: int = W, h: int = H, ground: int = GROUND) -> Image.Image:
    tile_w = w + period * 2
    img = Image.new("RGBA", (tile_w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, ground, tile_w, h), fill=(16, 8, 22, 255))
    m = Image.new("L", (tile_w, h), 0)
    dm = ImageDraw.Draw(m)
    dm.line((0, ground, tile_w, ground), fill=255, width=3)
    for x in range(0, tile_w, period):
        dm.line((x, ground + 16, x + period // 2, ground + 16), fill=150, width=2)
    img.alpha_composite(neon.glow(m, neon.ORANGE, 3))
    return img


def _scroll(dst, layer, offset: float, period: int):
    """Paste a horizontally repeating layer shifted left by ``offset`` pixels."""
    x = -int(offset % period)
    dst.alpha_composite(layer.crop((-x, 0, -x + dst.width, layer.height)) if layer.width >= dst.width - x else layer,
                        (0, 0))


def world(t_px: float, w: int = W, h: int = H, ground: int = GROUND, with_sky=True) -> Image.Image:
    """The background after the camera travelled ``t_px`` pixels."""
    img = sky(w, h).copy() if with_sky else Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _scroll(img, hills(340, h, ground), t_px * 0.25, 340)
    _scroll(img, graveyard(190, h, ground), t_px * 0.6, 190)
    _scroll(img, ground_strip(48, w, h, ground), t_px, 48)
    return img


# --------------------------------------------------------------------------- hero
@lru_cache(maxsize=32)
def hero(phase: int, size: int = 64, pose: str = "run") -> Image.Image:
    """Pumpkin-head hero with a cape; ``phase`` 0..5 animates the run cycle."""
    pad = 18
    cw, ch = size + 2 * pad, int(size * 1.36) + 2 * pad
    m = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(m)
    cx = cw // 2
    head_r = size * 0.28
    hy = pad + head_r
    body_top, hip = hy + head_r, hy + head_r + size * 0.42
    a = math.sin(phase / 6 * math.tau)
    if pose == "jump":
        a = 0.9
    if pose == "fall":
        a = 0.0
    lw = max(4, size // 13)
    d.line((cx, body_top, cx, hip), fill=255, width=lw)
    leg = size * 0.36
    for s in (1, -1):  # legs
        ang = (0.55 * a * s) if pose == "run" else (0.6 * s if pose == "jump" else 1.2 * s)
        d.line((cx, hip, cx + leg * math.sin(ang), hip + leg * math.cos(ang)), fill=255, width=lw)
    arm = size * 0.3
    for s in (1, -1):  # arms swing against the legs
        ang = -0.7 * a * s if pose == "run" else (-2.4 * s if pose == "jump" else 1.4 * s)
        d.line((cx, body_top + 6, cx + arm * math.sin(ang), body_top + 6 + arm * math.cos(ang)), fill=255, width=lw)
    # cape flapping behind
    flap = 6 * math.sin(phase / 6 * math.tau * 2)
    d.line((cx - 2, body_top + 2, cx - size * 0.38, hip + 4 + flap, cx - 4, hip - 2), fill=255, width=2)
    body = neon.glow(m, neon.CYAN, 3)
    head = neon.icon_light("pumpkin_lit", int(head_r * 2.6), neon.ORANGE)
    body.alpha_composite(head, (cx - head.width // 2, int(hy - head.height / 2)))
    return body


def place(img, sprite, x, foot_y):
    img.alpha_composite(sprite, (round(x - sprite.width / 2), round(foot_y - sprite.height + 18)))


# --------------------------------------------------------------------------- cutscene
def _gif(frames, durations) -> bytes:
    rgb = [f.convert("RGB") for f in frames]
    keys = [rgb[0], rgb[len(rgb) // 2], rgb[-1]]
    mosaic = Image.new("RGB", (W, H * len(keys)))
    for i, f in enumerate(keys):
        mosaic.paste(f, (0, H * i))
    pal = mosaic.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb]
    buf = BytesIO()
    out[0].save(buf, format="GIF", save_all=True, append_images=out[1:], duration=durations, optimize=True)
    return buf.getvalue()


def cutscene_frames(monster: str, color: tuple, won: bool, candies: int = 0, headline: str = "",
                    subline: str = "", seed: int = 0):
    rnd = random.Random(seed)
    frames, durations = [], []
    speed = 14
    mon_size = 92
    mons = neon.icon_light(monster, mon_size, tuple(color))
    hero_x, travel = 150, 0.0
    candy = neon.icon_light("candy", 30, neon.PINK)
    shake = 0
    # 1. run in, the monster comes into view
    for f in range(12):
        travel += speed
        img = world(travel)
        mx = W + 60 - (W + 60 - 500) * min(1.0, f / 10)
        place(img, mons, mx, GROUND + 4 * math.sin(f))
        place(img, hero(f % 6), hero_x, GROUND)
        frames.append(img)
        durations.append(70)
    mx = 500
    if won:
        # 2. jump attack
        for f in range(6):
            t = (f + 1) / 6
            x = hero_x + (mx - 60 - hero_x) * t
            y = GROUND - 110 * math.sin(math.pi * min(1.0, t * 0.9))
            img = world(travel)
            place(img, mons, mx, GROUND)
            place(img, hero(0, pose="jump"), x, y)
            frames.append(img)
            durations.append(60)
        # 3. burst: the monster explodes into candies that fly to the hero
        parts = [(rnd.uniform(0, math.tau), rnd.uniform(4, 11)) for _ in range(26)]
        n_candy = min(10, max(3, candies // 40))
        flying = [(mx + rnd.uniform(-30, 30), GROUND - 50 + rnd.uniform(-30, 30)) for _ in range(n_candy)]
        hx = mx - 70
        for f in range(14):
            img = world(travel)
            if f == 0:
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for ang, v in parts:
                r = v * (f + 1)
                px, py = mx + r * math.cos(ang), GROUND - 50 + r * math.sin(ang) + 0.6 * (f ** 2)
                a = max(0, 255 - f * 18)
                od.ellipse((px - 3, py - 3, px + 3, py + 3), fill=tuple(color) + (a,))
            img.alpha_composite(over)
            t = min(1.0, f / 10)
            for sx, sy in flying:
                cx = sx + (hx - sx) * t
                cy = sy + (GROUND - 60 - sy) * t - 60 * math.sin(math.pi * t)
                if t < 1:
                    img.alpha_composite(candy, (round(cx - candy.width / 2), round(cy - candy.height / 2)))
            place(img, hero(f % 6 if f > 3 else 0, pose="run" if f > 3 else "jump"), hx,
                  GROUND - max(0, 40 - 10 * f))
            if f >= 6:
                k = min(1.0, (f - 5) / 4)
                size = int(30 + 18 * k)
                img.alpha_composite(_neon_layer((W, H), headline, (W // 2, 70), size, tuple(neon.YELLOW), "mm"))
                if subline:
                    img.alpha_composite(_neon_layer((W, H), subline, (W // 2, 118), 20, tuple(neon.PINK), "mm"))
            frames.append(img)
            durations.append(70)
    else:
        # 2. the monster charges, the hero is knocked back
        for f in range(10):
            t = (f + 1) / 10
            img = world(travel)
            shake = rnd.randint(-6, 6) if 3 <= f <= 6 else 0
            x = mx - (mx - hero_x - 40) * min(1.0, t * 1.6)
            place(img, mons, x + shake, GROUND)
            hx = hero_x - (60 * max(0.0, t - 0.4))
            place(img, hero(0, pose="fall" if t > 0.4 else "run"), hx + shake, GROUND + (10 if t > 0.5 else 0))
            if f >= 4:
                img.alpha_composite(_neon_layer((W, H), headline, (W // 2, 70), 40, tuple(neon.RED), "mm"))
                if subline:
                    img.alpha_composite(_neon_layer((W, H), subline, (W // 2, 118), 20, tuple(neon.PURPLE), "mm"))
            frames.append(img)
            durations.append(70 if f < 9 else 80)
    durations[-1] = 1800
    return frames, durations


def cutscene_gif(monster: str, color: tuple, won: bool, candies: int = 0, headline: str = "", subline: str = "",
                 seed: int = 0) -> bytes:
    frames, durations = cutscene_frames(monster, color, won, candies, headline, subline, seed)
    return _gif(frames, durations)
