"""Title screen of /jeux: a neon logo, and below it the hero running past glowing signposts."""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .cards import _neon_layer
from .scroller import _scroll, ground_strip, hero, hills, place

W, H = 760, 300
FLOOR = 280
SIGNS = [("QUIZ", neon.PINK), ("HASARD", neon.YELLOW), ("RÉFLEXES", neon.CYAN), ("AVENTURE", neon.GREEN),
         ("DÉFIS", neon.ORANGE), ("TRÉSORS", neon.PURPLE)]
SPACING = 190
LOOP = SPACING * len(SIGNS)  # one full loop of signposts
FRAMES = 30


@lru_cache(maxsize=1)
def _sky():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line((0, y, W, y), fill=(int(30 - 22 * k), int(8 - 4 * k), int(52 - 38 * k), 255))
    rnd = random.Random(11)
    for _ in range(90):
        x, y = rnd.randrange(W), rnd.randrange(170)
        v = rnd.randrange(110, 255)
        d.point((x, y), fill=(v, v, min(255, v + 40), 255))
    moon = Image.new("L", (W, H), 0)
    ImageDraw.Draw(moon).ellipse((W - 120, 20, W - 64, 76), fill=255)
    ImageDraw.Draw(moon).ellipse((W - 104, 14, W - 48, 70), fill=0)
    img.alpha_composite(neon.glow(moon, (255, 236, 170), 7))
    return img


@lru_cache(maxsize=1)
def _signposts() -> Image.Image:
    """One loop of signposts (twice, so the strip can scroll seamlessly)."""
    w = LOOP * 2
    img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    for rep in range(2):
        for k, (text, color) in enumerate(SIGNS):
            x = rep * LOOP + k * SPACING + 60
            m = Image.new("L", (w, H), 0)
            d = ImageDraw.Draw(m)
            d.line((x, FLOOR, x, FLOOR - 70), fill=255, width=4)
            box = (x - 52, FLOOR - 104, x + 52, FLOOR - 70)
            d.polygon([(box[0], box[1]), (box[2], box[1]), (box[2] + 14, (box[1] + box[3]) // 2), (box[2], box[3]),
                       (box[0], box[3])], outline=255)
            img.alpha_composite(neon.glow(m, color, 3))
            size = neon.fit_text(text, 18, 96)
            img.alpha_composite(_neon_layer((w, H), text, (x + 4, (box[1] + box[3]) // 2), size, tuple(color), "mm"))
    return img


def menu_frames():
    letters_title = "NUIT HANTÉE"
    logo = _neon_layer((W, H), letters_title, (W // 2, 62), neon.fit_text(letters_title, 64, 560), tuple(neon.ORANGE), "mm")
    sub = _neon_layer((W, H), "31 JEUX · 6 MONDES · 1 NUIT", (W // 2, 116), 20, tuple(neon.PURPLE), "mm")
    frame_m = neon.rounded_frame_mask((W, H), (110, 14, W - 110, 146), 24, 4)
    frame = neon.glow(frame_m, neon.PINK, 5)
    hill_layer = hills(285, H, FLOOR)
    ground = ground_strip(57, W, H, FLOOR)
    posts = _signposts()
    ghost_n = max(1, neon.icon_frames("ghost"))
    frames = []
    for i in range(FRAMES):
        t = i / FRAMES
        travel = LOOP * t
        img = _sky().copy()
        _scroll(img, hill_layer, travel * 0.25, 285)
        _scroll(img, posts, travel, LOOP)
        _scroll(img, ground, travel, 57)
        pulse = 0.8 + 0.2 * math.sin(t * math.tau * 2)
        img.alpha_composite(neon.dim(frame, pulse))
        img.alpha_composite(neon.dim(logo, 0.35 if i % 10 == 7 else 1.0))  # the sign buzzes now and then
        img.alpha_composite(sub)
        ghost = neon.icon_light("ghost", 54, neon.WHITE, int(t * ghost_n * 3) % ghost_n)
        img.alpha_composite(ghost, (34, round(FLOOR - 120 + 10 * math.sin(t * math.tau * 3))))
        place(img, hero(i % 4 * 2, 66), 190, FLOOR)
        frames.append(img)
    return frames
