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
@lru_cache(maxsize=96)
def hero(phase: int, size: int = 64, pose: str = "run") -> Image.Image:
    """Pumpkin-head hero in a tunic and a long cape, drawn as a filled neon sprite.

    ``phase`` 0..7 animates the run cycle (knees bend, arms swing, the cape flaps).
    Poses: run, jump, fall, idle, cheer (arms up), hit (recoils backwards),
    slide (low, legs first, leaning back) and strike (lunge with a punch forward).
    The feet stand 18 px above the bottom of the image (see :func:`place`).
    """
    k = 2  # drawn at twice the size, then reduced: smooth lines
    pad = 18
    u = size / 64 * k
    cw, ch = int(size * 1.6) + 2 * pad, int(size * 1.7) + 2 * pad
    big = (cw * k, ch * k)
    cape_f, body_f = Image.new("L", big, 0), Image.new("L", big, 0)
    cape_l, line = Image.new("L", big, 0), Image.new("L", big, 0)
    dcf, dbf, dcl, dl = (ImageDraw.Draw(i) for i in (cape_f, body_f, cape_l, line))
    p = phase / 8 * math.tau
    cx = big[0] / 2
    foot_y = big[1] - pad * k
    thigh = shin = 14 * u
    bob = 3 * u * abs(math.cos(p)) if pose == "run" else 0
    lean = {"run": 0.16, "jump": 0.05, "fall": -0.45, "idle": 0.0, "cheer": 0.0, "hit": -0.3, "slide": -0.75,
            "strike": 0.3}.get(pose, 0)
    hip = (cx, foot_y - thigh - shin + 2 * u - bob - (4 * u if pose == "jump" else 0))
    if pose == "slide":  # sitting low, the legs stretched forward
        hip = (cx - 6 * u, foot_y - 9 * u)
    top = (hip[0] + 26 * u * math.sin(lean), hip[1] - 26 * u * math.cos(lean))
    lw = max(3, int(4.5 * u))
    thin = max(2, int(3 * u))
    # cape, behind everything, flapping in the wind
    flap = 6 * u * math.sin(p * 2) + (8 * u if pose == "jump" else 0)
    cape = [(top[0] - 4 * u, top[1] + 2 * u), (top[0] - 12 * u, top[1] + 10 * u),
            (hip[0] - 26 * u - flap, hip[1] + 12 * u + flap / 2), (hip[0] - 34 * u - flap, hip[1] + 2 * u),
            (hip[0] - 18 * u, hip[1] - 16 * u)]
    dcf.polygon(cape, fill=255)
    dcl.line(cape + [cape[0]], fill=255, width=thin, joint="curve")

    def leg(angle, knee):
        kx, ky = hip[0] + thigh * math.sin(angle), hip[1] + thigh * math.cos(angle)
        a2 = angle - knee
        fx, fy = kx + shin * math.sin(a2), ky + shin * math.cos(a2)
        dl.line((hip, (kx, ky), (fx, fy)), fill=255, width=lw, joint="curve")
        boot = (fx - 3 * u, fy - 5 * u, fx + 9 * u, fy + 2 * u)
        dbf.rounded_rectangle(boot, radius=2 * u, fill=255)
        dl.rounded_rectangle(boot, radius=2 * u, outline=255, width=thin)

    if pose == "run":
        for off in (0.0, math.pi):
            leg(0.75 * math.sin(p + off), -(0.2 + 1.0 * max(0.0, math.cos(p + off))))
    elif pose == "jump":
        leg(1.0, -1.6)
        leg(-0.2, -1.1)
    elif pose in ("fall", "hit"):
        leg(1.2, -0.3)
        leg(0.7, -0.6)
    elif pose == "slide":
        leg(1.45, 0.05)
        leg(1.0, -0.9)
    elif pose == "strike":
        leg(0.7, -0.35)
        leg(-0.6, -0.25)
    else:
        leg(0.12, -0.05)
        leg(-0.12, -0.05)
    # tunic (a trapezoid from the shoulders to the belt)
    perp = (math.cos(lean), math.sin(lean))
    tunic = [(top[0] - 10 * u * perp[0], top[1] - 10 * u * perp[1]),
             (top[0] + 10 * u * perp[0], top[1] + 10 * u * perp[1]),
             (hip[0] + 9 * u, hip[1] + 4 * u), (hip[0] - 9 * u, hip[1] + 4 * u)]
    dbf.polygon(tunic, fill=255)
    dl.line(tunic + [tunic[0]], fill=255, width=thin, joint="curve")
    dl.line(((hip[0] - 9 * u, hip[1] - 2 * u), (hip[0] + 9 * u, hip[1] - 2 * u)), fill=255, width=thin)  # belt
    # arms
    sh = (top[0] + 4 * u * perp[0], top[1] + 5 * u)
    if pose == "run":
        arms = [(-1.0 * math.sin(p), 1.0), (1.0 * math.sin(p), 1.0)]
    elif pose in ("cheer", "jump"):
        arms = [(2.7, 0.3), (-2.7, -0.3)]
    elif pose in ("fall", "hit"):
        arms = [(2.3, -0.6), (-2.0, 0.6)]
    elif pose == "slide":
        arms = [(-2.0, 0.4), (2.2, -0.5)]
    elif pose == "strike":
        arms = [(1.62, 0.0), (-0.9, 0.7)]
    else:
        arms = [(0.25, 0.3), (-0.25, 0.3)]
    for a, bend in arms:
        ex, ey = sh[0] + 12 * u * math.sin(a), sh[1] + 12 * u * math.cos(a)
        hx, hy = ex + 11 * u * math.sin(a + bend), ey + 11 * u * math.cos(a + bend)
        dl.line((sh, (ex, ey), (hx, hy)), fill=255, width=lw, joint="curve")
        dbf.ellipse((hx - 4 * u, hy - 4 * u, hx + 4 * u, hy + 4 * u), fill=255)  # glove
        dl.ellipse((hx - 4 * u, hy - 4 * u, hx + 4 * u, hy + 4 * u), outline=255, width=thin)
    small = (cw, ch)
    out = Image.new("RGBA", small, (0, 0, 0, 0))
    for mask, color in ((cape_f, (70, 18, 96)), (body_f, (22, 38, 72))):
        layer = Image.new("RGBA", small, color + (255,))
        layer.putalpha(mask.resize(small, Image.LANCZOS))
        out.alpha_composite(layer)
    out.alpha_composite(neon.glow(cape_l.resize(small, Image.LANCZOS), neon.PURPLE, 2.2))
    out.alpha_composite(neon.glow(line.resize(small, Image.LANCZOS), neon.CYAN, 2.2))
    # the pumpkin head, with a dark core so the face reads clearly
    head_size = int(size * 0.66)
    head = neon.icon_light("pumpkin_lit", head_size, neon.ORANGE)
    core = Image.new("L", head.size, 0)
    r = head_size * 0.4
    hc = (head.width / 2, head.height / 2)
    ImageDraw.Draw(core).ellipse((hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r), fill=255)
    dark = Image.new("RGBA", head.size, (44, 18, 6, 255))
    dark.putalpha(core)
    hx = top[0] / k + 3 * math.sin(lean)
    hy = top[1] / k - head_size * 0.36
    pos = (round(hx - head.width / 2), round(hy - head.height / 2))
    out.alpha_composite(dark, pos)
    out.alpha_composite(head, pos)
    return out


def hud(img, name: str):
    """Video-game HUD: the player's name in the top-left corner."""
    if name:
        text = "▶ " + name.upper()[:20]
        img.alpha_composite(_neon_layer(img.size, text, (18, 20), 16, tuple(neon.CYAN), "lm"))


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
                    subline: str = "", seed: int = 0, name: str = ""):
    """End-of-game cutscene, with a random finishing move (or way of losing) and a random night sky."""
    from .scenes import night_bg  # late import: scenes builds on this module
    rnd = random.Random(seed)
    variant = rnd.randrange(5)
    move = rnd.choice(["stomp", "throw", "dash"]) if won else rnd.choice(["knock", "steal", "flee"])
    size = 76
    frames, durations = [], []
    mons = neon.icon_light(monster, 96, tuple(color))
    hero_x, travel, speed = 150, 0.0, 14
    candy = neon.icon_light("candy", 30, neon.PINK)
    mx = 500

    def bg():
        return night_bg(variant, travel)

    def title(img, f0, f, good):
        if f >= f0:
            k = min(1.0, (f - f0 + 1) / 4)
            img.alpha_composite(_neon_layer((W, H), headline, (W // 2, 64), int(neon.fit_text(headline, 44, 620) * (0.7 + 0.3 * k)),
                                            tuple(neon.YELLOW if good else neon.RED), "mm"))
            if subline:
                img.alpha_composite(_neon_layer((W, H), subline, (W // 2, 110), 20,
                                                tuple(neon.PINK if good else neon.PURPLE), "mm"))

    # 1. run in, the monster comes into view
    for f in range(11):
        travel += speed
        img = bg()
        x = W + 60 - (W + 60 - mx) * min(1.0, f / 9)
        place(img, mons, x, GROUND + 4 * math.sin(f))
        place(img, hero(f % 8, size), hero_x, GROUND)
        frames.append(img)
        durations.append(65)
    if won:
        hx = hero_x
        if move == "stomp":  # jump and land on its head
            for f in range(6):
                t = (f + 1) / 6
                img = bg()
                place(img, mons, mx, GROUND)
                hx = hero_x + (mx - 40 - hero_x) * t
                place(img, hero(0, size, "jump"), hx, GROUND - 120 * math.sin(math.pi * min(1.0, t * 0.9)))
                frames.append(img)
                durations.append(60)
        elif move == "throw":  # a glowing pumpkin flies in an arc and explodes
            bomb = neon.icon_light("pumpkin_lit", 44, neon.ORANGE)
            for f in range(7):
                t = (f + 1) / 7
                img = bg()
                place(img, mons, mx, GROUND)
                place(img, hero(0, size, "cheer" if f < 2 else "idle"), hero_x, GROUND)
                bx = hero_x + 30 + (mx - hero_x - 30) * t
                by = GROUND - 110 - 120 * math.sin(math.pi * t) + 80 * t
                rot = bomb.rotate(-60 * f, expand=True)
                img.alpha_composite(rot, (round(bx - rot.width / 2), round(by - rot.height / 2)))
                frames.append(img)
                durations.append(60)
        else:  # dash: the hero turns into a streak of light
            for f in range(5):
                t = (f + 1) / 5
                img = bg()
                place(img, mons, mx, GROUND)
                hx = hero_x + (mx - 60 - hero_x) * t
                for k in range(4):  # motion trail
                    ghost = neon.dim(hero(f % 8, size), 0.18 * (4 - k))
                    place(img, ghost, hx - 30 * (k + 1), GROUND)
                place(img, hero(f % 8, size), hx, GROUND)
                frames.append(img)
                durations.append(50)
        # burst: the monster explodes into candies flying to the hero
        parts = [(rnd.uniform(0, math.tau), rnd.uniform(4, 11)) for _ in range(28)]
        n_candy = min(12, max(3, candies // 40))
        flying = [(mx + rnd.uniform(-30, 30), GROUND - 50 + rnd.uniform(-30, 30)) for _ in range(n_candy)]
        hx = min(hx, mx - 70)
        for f in range(14):
            img = bg()
            if f == 0:
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for ang, v in parts:
                r = v * (f + 1)
                px, py = mx + r * math.cos(ang), GROUND - 50 + r * math.sin(ang) + 0.6 * (f ** 2)
                od.ellipse((px - 3, py - 3, px + 3, py + 3), fill=tuple(color) + (max(0, 255 - f * 18),))
            img.alpha_composite(over)
            t = min(1.0, f / 10)
            for sx, sy in flying:
                if t < 1:
                    cx = sx + (hx - sx) * t
                    cy = sy + (GROUND - 60 - sy) * t - 60 * math.sin(math.pi * t)
                    img.alpha_composite(candy, (round(cx - candy.width / 2), round(cy - candy.height / 2)))
            place(img, hero(0, size, "cheer" if f > 3 else "jump"), hx, GROUND - max(0, 40 - 10 * f))
            title(img, 6, f, True)
            frames.append(img)
            durations.append(70)
    else:
        bag = neon.icon_light("candy_bag", 44, neon.ORANGE)
        for f in range(12):
            t = (f + 1) / 12
            img = bg()
            shake = rnd.randint(-6, 6) if 3 <= f <= 6 and move != "flee" else 0
            if move == "flee":  # the hero runs away to the left, the monster chases him off-screen
                hx = hero_x - 260 * t
                place(img, hero(f % 8, size).transpose(Image.FLIP_LEFT_RIGHT), hx, GROUND)
                place(img, mons, mx - 300 * t, GROUND - 10 * abs(math.sin(f)))
            else:
                x = mx - (mx - hero_x - 40) * min(1.0, t * 1.6)
                place(img, mons, x + shake, GROUND)
                hx = hero_x - 60 * max(0.0, t - 0.4)
                place(img, hero(0, size, "fall" if t > 0.4 else "idle"), hx + shake, GROUND + (8 if t > 0.5 else 0))
                if move == "steal" and t > 0.4:  # the monster runs off with the candy bag
                    k = (t - 0.4) / 0.6
                    img.alpha_composite(bag, (round(x + 40 + 200 * k), round(GROUND - 110 - 60 * math.sin(math.pi * k))))
            if f in (4, 5) and move != "flee":
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 50, 60)))
            title(img, 4, f, False)
            frames.append(img)
            durations.append(75)
    durations[-1] = 1800
    for img in frames:
        hud(img, name)
    return frames, durations


def cutscene_gif(monster: str, color: tuple, won: bool, candies: int = 0, headline: str = "", subline: str = "",
                 seed: int = 0, name: str = "") -> bytes:
    frames, durations = cutscene_frames(monster, color, won, candies, headline, subline, seed, name)
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


def march_gif(team, caption, caption_color, rain=False, seed=0, name: str = "") -> bytes:
    frames, durations = march_frames(team, caption, caption_color, rain, seed)
    for img in frames:
        hud(img, name)
    return _gif(frames, durations)
