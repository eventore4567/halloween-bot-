"""Varied 2D action scenes: every room, object and outcome has its own look and animation.

``room_clip`` plays one choice in the haunted house: the hero runs through the
room (each room has its own decor), reaches the object he chose (door, chest,
lectern, cauldron…), opens it, and the outcome is animated in its own way
(candy fountain, spinning key, spider dropping from the ceiling, monster
leaping out, friendly ghost circling, dust cloud and a bat flying away…).
``grave_clip`` digs a grave in the cemetery, ``chest_clip`` opens the daily chest.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .cards import _neon_layer
from .scroller import GROUND, H, W, _gif, _scroll, ground_strip, hills, place, sky
from .scroller import hero as _hero

HERO_SIZE = 80


def hero(phase: int, pose: str = "run"):
    return _hero(phase, HERO_SIZE, pose)


# --------------------------------------------------------------------------- room decors
ROOM_DECOR = {
    "Le hall d'entrée": ("hall", neon.YELLOW),
    "La bibliothèque": ("library", neon.ORANGE),
    "La cuisine": ("kitchen", neon.GREEN),
    "La salle de bal": ("ballroom", neon.PINK),
    "Le grenier": ("attic", neon.PURPLE),
    "La cave": ("cellar", neon.ORANGE),
    "La chapelle": ("chapel", neon.CYAN),
    "La serre": ("greenhouse", neon.GREEN),
    "La chambre d'enfant": ("nursery", neon.PINK),
    "La galerie des portraits": ("gallery", neon.YELLOW),
}
PERIOD = 340


def _decor(d: ImageDraw.ImageDraw, kind: str, x0: int):
    """Neon line drawings of one decor tile starting at ``x0`` (on a 340 px period)."""
    g = GROUND
    if kind == "hall":
        d.line((x0 + 100, 0, x0 + 100, 40), fill=255, width=2)  # chandelier
        d.arc((x0 + 60, 20, x0 + 140, 70), 0, 180, fill=255, width=3)
        for k in range(5):
            cx = x0 + 66 + k * 17
            d.line((cx, 50, cx, 40), fill=255, width=2)
        for k in range(6):  # stairs
            d.line((x0 + 200 + k * 20, g - k * 18, x0 + 220 + k * 20, g - k * 18), fill=255, width=3)
            d.line((x0 + 220 + k * 20, g - k * 18, x0 + 220 + k * 20, g - (k + 1) * 18), fill=255, width=3)
    elif kind == "library":
        for s in (0, 1):
            bx = x0 + 30 + s * 170
            d.rectangle((bx, 50, bx + 130, g), outline=255, width=3)
            for row in range(4):
                y = 50 + row * 48
                d.line((bx, y + 48, bx + 130, y + 48), fill=255, width=2)
                for b in range(9):
                    hgt = 30 + (b * 7 + row * 5) % 14
                    d.line((bx + 8 + b * 13, y + 46, bx + 8 + b * 13, y + 46 - hgt), fill=255, width=4)
    elif kind == "kitchen":
        d.line((x0 + 20, 60, x0 + 320, 60), fill=255, width=3)  # rail
        for k, r in enumerate((14, 20, 12, 18)):  # hanging pans
            cx = x0 + 50 + k * 70
            d.line((cx, 60, cx, 80), fill=255, width=2)
            d.ellipse((cx - r, 80, cx + r, 80 + r * 2), outline=255, width=3)
        d.rectangle((x0 + 30, 140, x0 + 300, 150), outline=255, width=2)  # shelf
        for k in range(6):
            cx = x0 + 50 + k * 42
            d.rounded_rectangle((cx, 110, cx + 22, 140), 5, outline=255, width=2)  # jars
    elif kind == "ballroom":
        for k in (0, 1):
            cx = x0 + 80 + k * 180
            d.line((cx, 0, cx, 30), fill=255, width=2)
            for r in (30, 18):
                d.arc((cx - r, 30 - r // 2, cx + r, 30 + r), 0, 180, fill=255, width=2)
        for k in (0, 1):  # tall arched windows
            wx = x0 + 30 + k * 180
            d.rectangle((wx, 90, wx + 50, g - 20), outline=255, width=2)
            d.arc((wx, 65, wx + 50, 115), 180, 360, fill=255, width=2)
    elif kind == "attic":
        d.line((x0, 20, x0 + PERIOD // 2, 120), fill=255, width=4)  # roof beams
        d.line((x0 + PERIOD // 2, 120, x0 + PERIOD, 20), fill=255, width=4)
        d.ellipse((x0 + 140, 40, x0 + 200, 100), outline=255, width=3)  # round window
        d.line((x0 + 170, 40, x0 + 170, 100), fill=255, width=2)
        d.line((x0 + 140, 70, x0 + 200, 70), fill=255, width=2)
        for k in range(5):  # cobweb in the corner
            d.line((x0, 0, x0 + 70 * math.cos(k * 0.38), 70 * math.sin(k * 0.38)), fill=255, width=1)
        for r in (25, 45, 65):
            d.arc((x0 - r, -r, x0 + r, r), 0, 90, fill=255, width=1)
    elif kind == "cellar":
        for k in (0, 1):  # vaulted arches
            ax = x0 + 20 + k * 170
            d.arc((ax, 30, ax + 150, 180), 180, 360, fill=255, width=3)
            d.line((ax, 105, ax, g), fill=255, width=3)
        for k in range(3):  # barrels
            bx = x0 + 60 + k * 80
            d.ellipse((bx, g - 60, bx + 50, g), outline=255, width=3)
            d.line((bx + 4, g - 40, bx + 46, g - 40), fill=255, width=2)
            d.line((bx + 4, g - 20, bx + 46, g - 20), fill=255, width=2)
    elif kind == "chapel":
        for k in (0, 1):  # stained glass
            wx = x0 + 40 + k * 170
            d.rectangle((wx, 80, wx + 60, 180), outline=255, width=3)
            d.arc((wx, 50, wx + 60, 110), 180, 360, fill=255, width=3)
            d.line((wx + 30, 50, wx + 30, 180), fill=255, width=2)
            d.line((wx, 130, wx + 60, 130), fill=255, width=2)
        d.line((x0 + 170, 40, x0 + 170, 80), fill=255, width=3)  # cross
        d.line((x0 + 156, 52, x0 + 184, 52), fill=255, width=3)
    elif kind == "greenhouse":
        for k in range(6):  # glass panes
            d.line((x0 + k * 57, 30, x0 + k * 57, g - 60), fill=255, width=2)
        d.line((x0, 30, x0 + PERIOD, 30), fill=255, width=2)
        d.line((x0, 110, x0 + PERIOD, 110), fill=255, width=1)
        for k in range(3):  # plants in pots
            px = x0 + 50 + k * 110
            d.polygon([(px, g), (px + 36, g), (px + 42, g - 34), (px - 6, g - 34)], outline=255)
            for a in (-0.6, 0, 0.6):
                d.line((px + 18, g - 34, px + 18 + 40 * math.sin(a), g - 34 - 50 * math.cos(a)), fill=255, width=3)
    elif kind == "nursery":
        d.rectangle((x0 + 40, 60, x0 + 120, 130), outline=255, width=3)  # window
        d.line((x0 + 80, 60, x0 + 80, 130), fill=255, width=2)
        hx = x0 + 200  # rocking horse
        d.arc((hx - 10, g - 30, hx + 80, g + 10), 200, 340, fill=255, width=3)
        d.line((hx + 20, g - 26, hx + 20, g - 60), fill=255, width=3)
        d.line((hx + 50, g - 26, hx + 50, g - 60), fill=255, width=3)
        d.line((hx + 10, g - 60, hx + 64, g - 60), fill=255, width=4)
        d.ellipse((hx + 56, g - 84, hx + 82, g - 58), outline=255, width=3)
    else:  # gallery: portraits whose eyes follow you
        for k in range(3):
            fx = x0 + 30 + k * 105
            d.rectangle((fx, 60, fx + 70, 150), outline=255, width=3)
            d.ellipse((fx + 22, 90, fx + 32, 98), fill=255)
            d.ellipse((fx + 40, 90, fx + 50, 98), fill=255)


@lru_cache(maxsize=12)
def room_layer(kind: str, color: tuple) -> Image.Image:
    w = PERIOD * 3
    img = neon.wall(w, H, sum(map(ord, kind)) % 5).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (w, H), (8, 3, 14, 125)))
    m = Image.new("L", (w, H), 0)
    d = ImageDraw.Draw(m)
    for k in range(3):
        _decor(d, kind, k * PERIOD)
    img.alpha_composite(neon.dim(neon.glow(m, color, 3), 0.62))
    return img


def room_bg(kind: str, color, t_px: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _scroll(img, room_layer(kind, tuple(color)), t_px * 0.5, PERIOD)
    _scroll(img, ground_strip(48, W, H, GROUND), t_px, 48)
    return img


# --------------------------------------------------------------------------- outdoor variants
@lru_cache(maxsize=16)
def _night(variant: int) -> Image.Image:
    rnd = random.Random(variant)
    img = sky(W, H).copy() if variant == 0 else Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if variant:
        d = ImageDraw.Draw(img)
        top = rnd.choice([(30, 8, 50), (8, 20, 46), (40, 10, 20), (10, 30, 30)])
        for y in range(H):
            k = y / H
            d.line((0, y, W, y), fill=tuple(int(c * (1 - 0.7 * k)) for c in top) + (255,))
        for _ in range(60):
            x, y = rnd.randrange(W), rnd.randrange(int(H * 0.6))
            v = rnd.randrange(120, 255)
            d.point((x, y), fill=(v, v, v, 255))
        mx, r = rnd.randrange(80, W - 80), rnd.randrange(22, 42)
        moon = Image.new("L", (W, H), 0)
        ImageDraw.Draw(moon).ellipse((mx - r, 30, mx + r, 30 + 2 * r), fill=255)
        if rnd.random() < 0.5:  # crescent
            ImageDraw.Draw(moon).ellipse((mx - r + r // 2, 24, mx + r + r // 2, 24 + 2 * r), fill=0)
        img.alpha_composite(neon.glow(moon, rnd.choice([(255, 236, 170), (200, 230, 255), (255, 170, 120)]), 8))
    return img


@lru_cache(maxsize=8)
def _tombs(style: int) -> Image.Image:
    w = 190 * 4
    m = Image.new("L", (w, H), 0)
    d = ImageDraw.Draw(m)
    rnd = random.Random(style)
    for k in range(8):
        x = k * 95 + rnd.randint(5, 30)
        kind = (k + style) % 4
        if kind == 0:
            d.rounded_rectangle((x, GROUND - 44, x + 30, GROUND), 12, outline=255, width=3)
        elif kind == 1:
            d.line((x + 14, GROUND - 54, x + 14, GROUND), fill=255, width=3)
            d.line((x, GROUND - 40, x + 28, GROUND - 40), fill=255, width=3)
        elif kind == 2:
            d.polygon([(x + 4, GROUND), (x + 26, GROUND), (x + 20, GROUND - 60), (x + 15, GROUND - 70),
                       (x + 10, GROUND - 60)], outline=255)
        else:
            d.line((x + 20, GROUND, x + 20, GROUND - 80), fill=255, width=4)
            d.line((x + 20, GROUND - 52, x + 42, GROUND - 76), fill=255, width=3)
            d.line((x + 20, GROUND - 62, x, GROUND - 86), fill=255, width=3)
    return neon.dim(neon.glow(m, rnd.choice([neon.GREEN, neon.CYAN, neon.PURPLE]), 3), 0.72)


def night_bg(variant: int, t_px: float) -> Image.Image:
    img = _night(variant).copy()
    _scroll(img, hills(340, H, GROUND), t_px * 0.25, 340)
    _scroll(img, _tombs(variant % 4), t_px * 0.6, 190)
    _scroll(img, ground_strip(48, W, H, GROUND), t_px, 48)
    return img


# --------------------------------------------------------------------------- props
PROP_OF = {"door": "door", "chest": "chest", "book": "lectern", "scroll": "lectern", "cauldron": "cauldron",
           "bone": "slab", "tomb": "slab", "potion_red": "barrel", "candle": "altar", "gift": "giftbox",
           "mushroom": "plant", "frog": "plant", "web": "web", "spider": "web", "crown": "frame", "key": "piano",
           "ghost_still": "door", "eye": "frame", "moon": "door", "lightning": "door", "bat": "door",
           "skull": "giftbox"}


def prop(kind: str, opened: float, color, t: float = 0.0) -> Image.Image:
    s = 160
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    b = s - 2
    o = opened
    if kind == "door":
        d.rectangle((44, 14, 116, b), outline=255, width=4)
        d.arc((44, -10, 116, 40), 180, 360, fill=255, width=4)
        leaf = 72 * (1 - o)
        d.polygon([(44, 14), (44 + leaf, 14 + 12 * o), (44 + leaf, b - 12 * o), (44, b)], outline=255)
        if o < 0.5:
            d.ellipse((44 + leaf - 14, 88, 44 + leaf - 6, 96), fill=255)
    elif kind == "chest":
        d.rectangle((30, 90, 130, b), outline=255, width=4)
        lift = 55 * o
        d.polygon([(30, 90), (130, 90), (130 - 12 * o, 90 - lift), (30 + 12 * o, 90 - lift)], outline=255)
        d.rectangle((72, 102, 88, 120), outline=255, width=3)
    elif kind == "lectern":
        d.line((80, b, 80, 90), fill=255, width=5)
        d.line((56, b, 104, b), fill=255, width=4)
        d.polygon([(40, 90), (120, 90), (110, 70), (50, 70)], outline=255)
        pages = 18 * o
        d.arc((50, 50 - pages, 80, 80), 180, 360, fill=255, width=3)
        d.arc((80, 50 - pages, 110, 80), 180, 360, fill=255, width=3)
    elif kind == "cauldron":
        d.ellipse((30, 80, 130, b), outline=255, width=4)
        d.line((30, 92, 130, 92), fill=255, width=4)
        for k in range(4):  # bubbles
            r = 4 + 3 * ((k + int(t * 6)) % 3)
            bx, by = 50 + k * 18, 80 - 20 * o - (k % 2) * 14 - (t * 40 % 20)
            d.ellipse((bx - r, by - r, bx + r, by + r), outline=255, width=2)
    elif kind == "slab":
        d.rectangle((24, b - 18, 136, b), outline=255, width=4)
        lift = 40 * o
        d.polygon([(24, b - 18), (136, b - 18 - lift), (136, b - 30 - lift), (24, b - 30)], outline=255)
    elif kind == "barrel":
        d.ellipse((40, 60, 120, b), outline=255, width=4)
        d.line((44, 90, 116, 90), fill=255, width=3)
        d.line((44, 130, 116, 130), fill=255, width=3)
        if o:
            d.ellipse((60 - 10 * o, 54 - 30 * o, 100 + 10 * o, 70 - 30 * o), outline=255, width=3)
    elif kind == "altar":
        d.rectangle((30, 100, 130, b), outline=255, width=4)
        for k, cx in enumerate((50, 80, 110)):
            d.line((cx, 100, cx, 70), fill=255, width=5)
            if o > k / 3:
                d.ellipse((cx - 6, 50, cx + 6, 68), outline=255, width=3)
    elif kind == "giftbox":
        d.rectangle((44, 90, 116, b), outline=255, width=4)
        d.line((80, 90, 80, b), fill=255, width=3)
        lid = 50 * o
        d.rectangle((38, 76 - lid, 122, 90 - lid), outline=255, width=4)
    elif kind == "plant":
        d.polygon([(50, b), (110, b), (120, 110), (40, 110)], outline=255)
        for a in (-0.7, -0.2, 0.3, 0.8):
            ln = 60 + 20 * o
            d.line((80, 110, 80 + ln * math.sin(a), 110 - ln * math.cos(a)), fill=255, width=4)
    elif kind == "web":
        for k in range(7):
            a = k / 6 * math.pi
            d.line((80, 20, 80 + 70 * math.cos(a), 20 + 70 * math.sin(a)), fill=255, width=2)
        for r in (25, 45, 65):
            d.arc((80 - r, 20 - r, 80 + r, 20 + r), 0, 180, fill=255, width=2)
        if o:
            d.line((80, 20, 80, 20 + 110 * o), fill=255, width=1)
    elif kind == "piano":
        d.rectangle((24, 70, 136, 130), outline=255, width=4)
        d.line((30, 130, 30, b), fill=255, width=4)
        d.line((130, 130, 130, b), fill=255, width=4)
        lid = 40 * o
        d.line((24, 70, 136, 70 - lid), fill=255, width=4)
        for k in range(8):
            d.line((34 + k * 13, 110, 34 + k * 13, 128), fill=255, width=2)
    else:  # frame
        d.rectangle((36, 30, 124, 130), outline=255, width=5)
        d.ellipse((60, 70, 72, 80), fill=255)
        d.ellipse((88, 70, 100, 80), fill=255)
        tilt = 20 * o
        d.line((80, 10, 36 + tilt, 30), fill=255, width=2)
        d.line((80, 10, 124 + tilt, 30), fill=255, width=2)
    return neon.glow(m, tuple(color), 4)


def put_prop(img, p, x):
    img.alpha_composite(p, (round(x - p.width / 2), GROUND - p.height + 2))


# --------------------------------------------------------------------------- outcomes
CAPTIONS = {
    "treasure": ["UNE FONTAINE DE BONBONS !", "LE JACKPOT DE LA PIÈCE !", "DES BONBONS PARTOUT !"],
    "key": ["LA CLÉ DE LA CRYPTE !", "UNE CLÉ ENSORCELÉE !"],
    "item": ["UN OBJET MAGIQUE !", "UN CADEAU DES ESPRITS !"],
    "trap": ["UN PIÈGE !", "AÏE, UNE ARAIGNÉE !", "C'ÉTAIT UN PIÈGE !"],
    "monster": ["UN MONSTRE BONDIT !", "ATTAQUE SURPRISE !", "IL T'A VU !"],
    "ghost": ["UN FANTÔME AMI", "UN ESPRIT BIENVEILLANT"],
    "empty": ["RIEN… JUSTE DE LA POUSSIÈRE", "UNE CHAUVE-SOURIS S'ENVOLE", "PERSONNE… POUR L'INSTANT"],
}
MONSTERS = ["demon", "vampire", "werewolf", "zombie", "mummy", "pumpkin_angry", "skull_fire"]


def _caption(img, text, good, k=1.0, sub=""):
    size = int(neon.fit_text(text, 34, 620) * (0.75 + 0.25 * k))
    img.alpha_composite(_neon_layer((W, H), text, (W // 2, 44), size, tuple(neon.YELLOW if good else neon.RED), "mm"))
    if sub:
        img.alpha_composite(_neon_layer((W, H), sub, (W // 2, 84), 18, tuple(neon.PINK if good else neon.PURPLE), "mm"))


def _particles(img, pts, color, alpha):
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for x, y, r in pts:
        od.ellipse((x - r, y - r, x + r, y + r), fill=tuple(color) + (max(0, min(255, int(alpha))),))
    img.alpha_composite(over)


def outcome_frames(bg, kind, prop_img, px, hx, label, sub, rnd, n=12):
    """Frames of an outcome animation in front of the opened prop."""
    good = kind in ("treasure", "key", "item", "ghost", "empty")
    frames = []
    if kind == "treasure":
        candy = neon.icon_light("candy", 30, neon.PINK)
        drops = [(rnd.uniform(-1.2, 1.2), rnd.uniform(6, 10), rnd.uniform(0, 0.3)) for _ in range(14)]
        for f in range(n):
            img = bg(f)
            put_prop(img, prop_img, px)
            for vx, vy, delay in drops:
                t = max(0.0, f / n - delay) * 1.6
                x = px + vx * 160 * t
                y = min(GROUND - 12, GROUND - 90 - vy * 60 * t + 220 * t * t)  # they pile up on the floor
                if t > 0:
                    img.alpha_composite(candy, (round(x - 15), round(y - 15)))
            place(img, hero(0, pose="cheer" if f > 3 else "idle"), hx, GROUND - (14 if f in (4, 5) else 0))
            _caption(img, label, True, min(1.0, f / 4), sub)
            frames.append(img)
    elif kind in ("key", "item"):
        icon = neon.icon_light("key" if kind == "key" else "gift", 80, neon.YELLOW if kind == "key" else neon.PINK)
        for f in range(n):
            img = bg(f)
            put_prop(img, prop_img, px)
            rays = Image.new("L", (W, H), 0)
            rd = ImageDraw.Draw(rays)
            cy = GROUND - 140
            for k in range(10):
                a = k / 10 * math.tau + f * 0.15
                rd.line((px, cy, px + 70 * math.cos(a), cy + 70 * math.sin(a)), fill=200, width=2)
            img.alpha_composite(neon.dim(neon.glow(rays, neon.YELLOW, 3), min(1.0, f / 5) * 0.6))
            sx = max(0.15, abs(math.cos(f * 0.5)))  # spinning
            spr = icon.resize((max(2, int(icon.width * sx)), icon.height))
            rise = min(1.0, (f + 1) / 5)
            img.alpha_composite(spr, (round(px - spr.width / 2), round(GROUND - 60 - 80 * rise - spr.height / 2)))
            place(img, hero(0, pose="cheer" if f > 4 else "idle"), hx, GROUND)
            _caption(img, label, True, min(1.0, f / 4), sub)
            frames.append(img)
    elif kind == "trap":
        spider = neon.icon_light("spider", 70, neon.RED)
        for f in range(n):
            img = bg(f)
            put_prop(img, prop_img, px)
            t = min(1.0, (f + 1) / 6)
            sy = -40 + (GROUND - 80) * t
            thread = Image.new("L", (W, H), 0)
            ImageDraw.Draw(thread).line((hx + 10, 0, hx + 10, sy), fill=200, width=1)
            img.alpha_composite(neon.glow(thread, (220, 220, 230), 1))
            img.alpha_composite(spider, (round(hx + 10 - spider.width / 2), round(sy - spider.height / 2)))
            if f >= 5:
                if f in (5, 6):
                    img.alpha_composite(Image.new("RGBA", (W, H), (255, 40, 60, 60)))
                drops = [(hx - 20 - 8 * k, GROUND - 40 + (f - 5) * 12 + k * 3, 4) for k in range(4)]
                _particles(img, drops, neon.PINK, 255 - (f - 5) * 30)
            place(img, hero(0, pose="hit" if f >= 5 else "idle"), hx - (min(30, (f - 4) * 8) if f > 4 else 0), GROUND)
            _caption(img, label, False, min(1.0, f / 4), sub)
            frames.append(img)
    elif kind == "monster":
        mon = neon.icon_light(rnd.choice(MONSTERS), 100, neon.RED)
        for f in range(n):
            t = min(1.0, (f + 1) / 6)
            shake = rnd.randint(-7, 7) if 4 <= f <= 7 else 0
            img = bg(f)
            put_prop(img, prop_img, px + shake)
            mx = px - (px - hx - 50) * t
            my = GROUND - 20 - 120 * math.sin(math.pi * t)
            img.alpha_composite(mon, (round(mx - mon.width / 2 + shake), round(my - mon.height / 2)))
            if f in (5, 6):
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 50, 70)))
            place(img, hero(0, pose="fall" if f >= 6 else "idle"), hx - (min(50, (f - 5) * 12) if f > 5 else 0) + shake,
                  GROUND)
            _caption(img, label, False, min(1.0, f / 4), sub)
            frames.append(img)
    elif kind == "ghost":
        ghost = neon.icon_light("ghost", 70, neon.CYAN)
        for f in range(n):
            img = bg(f)
            put_prop(img, prop_img, px)
            a = f / n * math.tau * 1.3
            gx = (px + hx) / 2 + 110 * math.cos(a)
            gy = GROUND - 120 + 40 * math.sin(a * 2)
            img.alpha_composite(ghost, (round(gx - ghost.width / 2), round(gy - ghost.height / 2)))
            trail = [(gx - 20 * math.cos(a) * k / 3, gy + 6 * k, 3) for k in range(1, 4)]
            _particles(img, trail, neon.CYAN, 120)
            place(img, hero(0, pose="cheer" if f > 6 else "idle"), hx, GROUND)
            _caption(img, label, True, min(1.0, f / 4), sub)
            frames.append(img)
    else:  # empty: dust, then a bat flies away
        bat_frames = max(1, neon.icon_frames("bat"))
        puffs = [(rnd.uniform(-50, 50), rnd.uniform(-30, 10), rnd.uniform(10, 22)) for _ in range(10)]
        for f in range(n):
            img = bg(f)
            put_prop(img, prop_img, px)
            k = (f + 1) / n
            dust = [(px + dx * (1 + k), GROUND - 50 + dy - 30 * k, r * (0.6 + k)) for dx, dy, r in puffs]
            _particles(img, dust, (130, 120, 140), 150 * (1 - k))
            bat = neon.icon_light("bat", 56, neon.PURPLE, f % bat_frames)
            bx, by = px + 260 * k, GROUND - 120 - 140 * k + 12 * math.sin(f * 1.4)
            img.alpha_composite(bat, (round(bx - bat.width / 2), round(by - bat.height / 2)))
            place(img, hero(0, pose="idle"), hx, GROUND)
            _caption(img, label, True, min(1.0, f / 4), sub)
            frames.append(img)
    return frames, good


def _approach(bg, prop_kind, color, n_run=9, px_end=470, hx_end=330, open_frames=6):
    """The hero runs in while the object slides into view, then opens it."""
    frames = []
    for f in range(n_run):
        img = bg(f * 14)
        px = W + 90 - (W + 90 - px_end) * min(1.0, (f + 1) / n_run)
        put_prop(img, prop(prop_kind, 0, color, f / 10), px)
        place(img, hero(f % 8), hx_end - 20 + 20 * min(1.0, f / n_run), GROUND)
        frames.append(img)
    for f in range(open_frames):
        t = (f + 1) / open_frames
        img = bg(n_run * 14)
        put_prop(img, prop(prop_kind, t, color, (n_run + f) / 10), px_end)
        place(img, hero(0, pose="idle" if f % 2 else "run"), hx_end, GROUND)
        frames.append(img)
    return frames


def _clip(frames_a, frames_b) -> bytes:
    frames = frames_a + frames_b
    durations = [65] * len(frames_a) + [80] * len(frames_b)
    durations[-1] = 1700
    return _gif(frames, durations)


def room_clip(room_name: str, choice_icon: str, kind: str, label: str | None = None, sub: str = "",
              seed: int = 0) -> bytes:
    """One choice in the haunted house, animated in the room's own decor."""
    rnd = random.Random(seed)
    decor, color = ROOM_DECOR.get(room_name, ("hall", neon.YELLOW))
    prop_kind = PROP_OF.get(choice_icon, "door")
    still = 9 * 14

    def bg(f):
        return room_bg(decor, color, still)

    frames_a = _approach(lambda t: room_bg(decor, color, t), prop_kind, color)
    frames_b, _good = outcome_frames(bg, kind, prop(prop_kind, 1, color), 470, 330,
                                     label or rnd.choice(CAPTIONS.get(kind, CAPTIONS["empty"])), sub, rnd)
    return _clip(frames_a, frames_b)


def grave_clip(kind: str, label: str, sub: str = "", seed: int = 0) -> bytes:
    """Digging a grave in the cemetery: a ghost spirals out, or a cursed chest bursts open."""
    rnd = random.Random(seed)
    variant = seed % 5
    color = rnd.choice([neon.GREEN, neon.CYAN, neon.PURPLE])
    frames_a = _approach(lambda t: night_bg(variant, t), "slab", color)
    outcome = "treasure" if kind == "chest" else "ghost"
    frames_b, _ = outcome_frames(lambda f: night_bg(variant, 9 * 14), outcome, prop("slab", 1, color), 470, 330,
                                 label, sub, rnd)
    return _clip(frames_a, frames_b)


def chest_clip(label: str, sub: str = "", streak: int = 1, seed: int = 0) -> bytes:
    """The daily chest: wooden at first, golden on a long streak."""
    rnd = random.Random(seed)
    variant = seed % 5
    color = [neon.ORANGE, neon.ORANGE, neon.PINK, neon.PINK, neon.CYAN, neon.CYAN, neon.YELLOW][min(6, streak - 1)]
    frames_a = _approach(lambda t: night_bg(variant, t), "chest", color)
    frames_b, _ = outcome_frames(lambda f: night_bg(variant, 9 * 14), "treasure", prop("chest", 1, color), 470, 330,
                                 label, sub, rnd)
    return _clip(frames_a, frames_b)
