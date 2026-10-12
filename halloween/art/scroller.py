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


# --------------------------------------------------------------------------- action scenes
@lru_cache(maxsize=4)
def _hall(period: int = 340) -> Image.Image:
    """Inside the haunted house: a dark brick wall with candle sconces, tiles every ``period``."""
    w = period * 3
    img = neon.wall(w, H, 4).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (w, H), (8, 3, 14, 120)))
    m = Image.new("L", (w, H), 0)
    d = ImageDraw.Draw(m)
    for k in range(3):
        x = k * period + 80
        d.rectangle((x - 3, 120, x + 3, 150), fill=255)  # sconce
        d.ellipse((x - 5, 104, x + 5, 120), outline=255, width=2)  # flame
        fx = k * period + 200  # picture frame
        d.rectangle((fx, 70, fx + 70, 150), outline=255, width=3)
    img.alpha_composite(neon.dim(neon.glow(m, neon.YELLOW, 3), 0.6))
    return img


def interior(t_px: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _scroll(img, _hall(340), t_px * 0.5, 340)
    _scroll(img, ground_strip(48, W, H, GROUND), t_px, 48)
    return img


def _prop(kind: str, opened: float, color) -> Image.Image:
    """A door, a tombstone or a chest, ``opened`` from 0 (closed) to 1 (open)."""
    s = 150
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    if kind == "door":
        d.rectangle((40, 18, 110, s - 2), outline=255, width=4)
        leaf = 70 * (1 - opened)
        d.polygon([(40, 18), (40 + leaf, 18 + 10 * opened), (40 + leaf, s - 2 - 10 * opened), (40, s - 2)], outline=255)
        if opened < 0.5:
            d.ellipse((40 + leaf - 14, 84, 40 + leaf - 6, 92), fill=255)
    elif kind == "tomb":
        d.rounded_rectangle((45, 40, 105, s - 2), 26, outline=255, width=4)
        d.line((62, 70, 88, 70), fill=255, width=3)
        if opened:
            d.arc((20, s - 30, 130, s + 20), 180, 360, fill=255, width=3)  # dug earth
    else:  # chest
        d.rectangle((30, 80, 120, s - 4), outline=255, width=4)
        lift = 50 * opened
        d.polygon([(30, 80), (120, 80), (120 - 10 * opened, 80 - lift), (30 + 10 * opened, 80 - lift)], outline=255)
        d.rectangle((68, 92, 82, 108), outline=255, width=3)
    return neon.glow(m, color, 4)


def _put_prop(img, prop_img, x):
    img.alpha_composite(prop_img, (round(x - prop_img.width / 2), GROUND - prop_img.height + 2))


def action_frames(prop: str, color, reveal: str, reveal_color, label: str, good: bool, inside=False, seed=0):
    rnd = random.Random(seed)
    bg = interior if inside else world
    frames, durations = [], []
    travel, speed = 0.0, 14
    px_end = 450
    for f in range(9):  # run towards the prop
        travel += speed
        img = bg(travel)
        px = W + 80 - (W + 80 - px_end) * min(1.0, (f + 1) / 9)
        _put_prop(img, _prop(prop, 0, color), px)
        place(img, hero(f % 6), 300, GROUND)
        frames.append(img)
        durations.append(65)
    dirt = [(rnd.uniform(-1, 1), rnd.uniform(3, 7)) for _ in range(14)]
    for f in range(6):  # open / dig
        img = bg(travel)
        t = (f + 1) / 6
        _put_prop(img, _prop(prop, t, color), px_end)
        place(img, hero(f % 2 * 3, pose="jump" if prop == "tomb" and f % 2 else "run"), 360, GROUND)
        if prop == "tomb":
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for vx, vy in dirt:
                x = px_end + vx * 40 * t
                y = GROUND - vy * 14 * math.sin(math.pi * t)
                od.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(150, 110, 70, 230))
            img.alpha_composite(over)
        frames.append(img)
        durations.append(80)
    icon = neon.icon_light(reveal, 86, tuple(reveal_color))
    for f in range(8):  # the reveal rises from the prop
        img = bg(travel)
        if f == 0:
            img.alpha_composite(Image.new("RGBA", (W, H), tuple(reveal_color) + (60,)))
        _put_prop(img, _prop(prop, 1, color), px_end)
        place(img, hero(0, pose="jump" if good and f in (2, 3) else ("fall" if not good and f > 2 else "run")),
              360 - (0 if good else min(30, 6 * f)), GROUND)
        rise = min(1.0, (f + 1) / 5)
        img.alpha_composite(icon, (px_end - icon.width // 2, round(GROUND - 70 - 70 * rise - icon.height / 2)))
        k = min(1.0, (f + 1) / 4)
        img.alpha_composite(_neon_layer((W, H), label, (W // 2, 46), int(24 + 12 * k),
                                        tuple(neon.YELLOW if good else neon.RED), "mm"))
        frames.append(img)
        durations.append(80)
    durations[-1] = 1500
    return frames, durations


def action_gif(prop: str, color, reveal: str, reveal_color, label: str, good: bool, inside=False, seed=0) -> bytes:
    """Short 2D clip of one action: the hero reaches a door / tomb / chest, it opens, something comes out."""
    frames, durations = action_frames(prop, color, reveal, reveal_color, label, good, inside, seed)
    return _gif(frames, durations)


# --------------------------------------------------------------------------- clash (duels)
def clash_frames(left: str, left_color, right: str, right_color, winner: int | None, caption: str, seed=0):
    """Two creatures charge at each other; the winner (0 left, 1 right, None draw) knocks the other away."""
    rnd = random.Random(seed)
    a = neon.icon_light(left, 96, tuple(left_color))
    b = neon.icon_light(right, 96, tuple(right_color)).transpose(Image.FLIP_LEFT_RIGHT)
    frames, durations = [], []
    meet = W // 2
    for f in range(9):  # charge
        t = (f + 1) / 9
        img = world(f * 4)
        xa = 60 + (meet - 56 - 60) * t * t
        xb = W - 60 - (W - 60 - meet - 56) * t * t
        hop = abs(math.sin(f * 1.3)) * 10
        img.alpha_composite(a, (round(xa - a.width / 2), round(GROUND - a.height + 14 - hop)))
        img.alpha_composite(b, (round(xb - b.width / 2), round(GROUND - b.height + 14 - hop)))
        frames.append(img)
        durations.append(60)
    sparks = [(rnd.uniform(0, math.tau), rnd.uniform(5, 12)) for _ in range(22)]
    for f in range(12):  # impact, then knock-back
        img = world(36)
        if f < 2:
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 110 - 50 * f)))
        over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(over)
        for ang, v in sparks:
            r = v * (f + 1)
            px, py = meet + r * math.cos(ang), GROUND - 50 + r * math.sin(ang)
            od.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(255, 240, 160, max(0, 255 - 22 * f)))
        img.alpha_composite(over)
        k = (f + 1) / 12
        for side, sprite in ((0, a), (1, b)):
            base = meet - 56 if side == 0 else meet + 56
            direction = -1 if side == 0 else 1
            if winner is None:  # both bounce back
                x, y, spr = base + direction * 70 * k, GROUND - 40 * math.sin(math.pi * k), sprite
            elif side == winner:  # the winner stands its ground, small victory hop
                x, y, spr = base, GROUND - 18 * abs(math.sin(k * math.pi * 2)), sprite
            else:  # the loser flies away spinning
                x = base + direction * 260 * k
                y = GROUND - 120 * math.sin(math.pi * min(1.0, k * 1.2))
                spr = sprite.rotate(direction * -300 * k, expand=True)
            img.alpha_composite(spr, (round(x - spr.width / 2), round(y - spr.height + 14)))
        if f >= 3:
            color = neon.YELLOW if winner is None else (left_color if winner == 0 else right_color)
            img.alpha_composite(_neon_layer((W, H), caption, (W // 2, 54), neon.fit_text(caption, 34, 620),
                                            tuple(color), "mm"))
        frames.append(img)
        durations.append(70)
    durations[-1] = 1500
    return frames, durations


def clash_gif(left, left_color, right, right_color, winner, caption, seed=0) -> bytes:
    frames, durations = clash_frames(left, left_color, right, right_color, winner, caption, seed)
    return _gif(frames, durations)


# --------------------------------------------------------------------------- march (expeditions)
def march_frames(team: list[tuple[str, tuple]], caption: str, caption_color, rain: bool = False, seed=0):
    """A team of monsters marching across the scrolling world; candies rain down on a happy return."""
    rnd = random.Random(seed)
    sprites = [neon.icon_light(icon, 70, tuple(color)) for icon, color in team] or [neon.icon_light("ghost", 70, neon.WHITE)]
    candy = neon.icon_light("candy", 28, neon.PINK)
    drops = [(rnd.uniform(40, W - 40), rnd.uniform(-H, 0), rnd.uniform(6, 12)) for _ in range(16)]
    frames, durations = [], []
    for f in range(20):
        img = world(f * 12)
        for k, spr in enumerate(sprites):
            x = 150 + k * 110
            hop = abs(math.sin((f + k * 2) * 0.9)) * 16
            img.alpha_composite(spr, (round(x - spr.width / 2), round(GROUND - spr.height + 12 - hop)))
        if rain:
            for x, y, v in drops:
                yy = (y + f * v * 6) % (GROUND + 30)
                img.alpha_composite(candy, (round(x), round(yy) - 30))
        if f >= 3:
            img.alpha_composite(_neon_layer((W, H), caption, (W // 2, 50), neon.fit_text(caption, 32, 620),
                                            tuple(caption_color), "mm"))
        frames.append(img)
        durations.append(80)
    durations[-1] = 1400
    return frames, durations


def march_gif(team, caption, caption_color, rain=False, seed=0) -> bytes:
    frames, durations = march_frames(team, caption, caption_color, rain, seed)
    return _gif(frames, durations)
