"""Animated GIF banners shown at the top of every panel.

All banners share one layout (night sky, moon, hills, big outlined title,
spaced subtitle, floating creatures) so the whole bot looks like one
product, while each game keeps its own colours and characters.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageFilter

from .canvas import Canvas, Grad, banner_gif_bytes
from .emoji_art import EMOJIS, render_frame

W, H = 800, 250
FRAMES = 12
SS = 2


@dataclass(frozen=True)
class Theme:
    title: str
    subtitle: str
    title_color: tuple
    title_color2: tuple
    sky: tuple = ((26, 12, 48), (70, 36, 120))
    hills: tuple = ((44, 22, 78), (24, 12, 44))
    left: tuple = ("pumpkin_lit",)
    right: tuple = ("ghost",)
    title_size: int = 74
    two_lines: bool = False
    accent: tuple = (255, 214, 102)
    moon: bool = True


ORANGE = ((255, 170, 60), (232, 96, 20))
GREEN = ((190, 255, 120), (70, 190, 70))
PURPLE = ((236, 170, 255), (170, 90, 255))
GOLD = ((255, 236, 140), (240, 160, 30))
RED = ((255, 140, 130), (220, 40, 60))
CYAN = ((180, 255, 250), (60, 200, 220))

THEMES: dict[str, Theme] = {
    "hub": Theme("NUIT HANTÉE", "LE GRAND JEU D'HALLOWEEN", *ORANGE,
                 left=("pumpkin_lit", "bat"), right=("ghost", "crystal")),
    "quiz": Theme("QUIZ MAUDIT", "{questions} QUESTIONS • 5 NIVEAUX", *ORANGE,
                  left=("pumpkin_angry",), right=("crystal", "bat")),
    "manor": Theme("LE MANOIR", "RÉVEILLE TES MONSTRES • RÉCOLTE DES ÂMES", *PURPLE,
                   left=("soul", "vampire"), right=("ghost", "werewolf")),
    "cauldron": Theme("L'ALCHIMISTE", "8 RECETTES SECRÈTES • CHANGENT À MINUIT", *GREEN,
                      left=("cauldron",), right=("potion_purple", "potion_green")),
    "wheel": Theme("ROUE DU DESTIN", "UN TOUR GRATUIT TOUTES LES 4 HEURES", *GOLD,
                   left=("wheel",), right=("star", "gem")),
    "memory": Theme("MÉMOIRE D'OUTRE-TOMBE", "RETROUVE LES 8 PAIRES", *CYAN, title_size=58,
                    left=("eye",), right=("tomb", "ghost")),
    "hunt": Theme("CHASSE AUX FANTÔMES", "ÉVITE LA FAUCHEUSE", *CYAN, title_size=60,
                  left=("ghost",), right=("reaper", "tomb")),
    "duel": Theme("DUEL DE MONSTRES", "VAMPIRE • LOUP-GAROU • CHASSEUR", *RED, title_size=64,
                  left=("vampire",), right=("werewolf", "hunter")),
    "hangman": Theme("LE PENDU", "SAUVE LE SQUELETTE", *GREEN,
                     left=("skull",), right=("coffin", "spider")),
    "daily": Theme("COFFRE DU JOUR", "REVIENS CHAQUE JOUR • SÉRIE BONUS", *GOLD,
                   left=("chest",), right=("candy_bag", "sparkle")),
    "shop": Theme("LA BOUTIQUE", "CHEZ LA SORCIÈRE MORGANE", *PURPLE,
                  left=("witch",), right=("potion_gold", "joker")),
    "top": Theme("LE PANTHÉON", "LES PLUS GRANDS MONSTRES DU SERVEUR", *GOLD,
                 left=("trophy",), right=("crown", "medal1")),
    "drop": Theme("APPARITION !", "LE PREMIER QUI CLIQUE GAGNE", *ORANGE,
                  left=("gift",), right=("ghost", "candy")),
    "boss": Theme("LE ROI CITROUILLE", "COMBAT DE SERVEUR • TOUS ENSEMBLE", *RED, title_size=64,
                  left=("pumpkin_angry",), right=("skull_fire", "bat")),
    "cards": Theme("CARTES MAUDITES", "COLLECTIONNE LES 24 MONSTRES", *PURPLE,
                   left=("gift",), right=("gem", "star")),
}


def _sky(theme: Theme, seed: int):
    c = Canvas(W, H, ss=SS)
    c.rect((0, 0, W, H), Grad(theme.sky[0], theme.sky[1], "v"))
    # soft horizontal bands like a painted sky
    for i, y in enumerate((70, 120, 160)):
        c.rect((0, y, W, y + 26 + i * 6), (255, 255, 255, 8 + i * 3))
    if theme.moon:
        c.circle(W - 150, 66, 60, (255, 240, 190, 26))
        c.circle(W - 150, 66, 44, (255, 240, 190, 40))
        c.circle(W - 150, 66, 32, Grad((255, 250, 220), (250, 214, 120), "radial"))
        c.circle(W - 158, 58, 6, (240, 205, 120))
        c.circle(W - 140, 76, 4, (240, 205, 120))
    rnd = random.Random(seed)
    # far hills
    pts = [(0, H)]
    for x in range(0, W + 41, 40):
        pts.append((x, 190 + 14 * math.sin(x / 70 + seed) + rnd.uniform(-4, 4)))
    pts.append((W, H))
    c.poly(pts, theme.hills[0])
    # tombstones & dead trees silhouettes
    for _ in range(6):
        x = rnd.uniform(20, W - 20)
        y = 200 + 14 * math.sin(x / 70 + seed)
        c.rect((x - 9, y - 22, x + 9, y + 10), theme.hills[1], radius=8)
    for x in (rnd.uniform(40, 200), rnd.uniform(560, 760)):
        y = 200 + 14 * math.sin(x / 70 + seed)
        c.line([(x, y + 5), (x, y - 50)], theme.hills[1], 6)
        c.line([(x, y - 30), (x - 22, y - 52)], theme.hills[1], 4)
        c.line([(x, y - 38), (x + 18, y - 62)], theme.hills[1], 4)
        c.line([(x - 12, y - 42), (x - 18, y - 60)], theme.hills[1], 3)
    # near wave
    pts = [(0, H)]
    for x in range(0, W + 21, 20):
        pts.append((x, 222 + 10 * math.sin(x / 55 + seed * 2)))
    pts.append((W, H))
    c.poly(pts, theme.hills[1])
    return c.result()


def _title_layer(theme: Theme, text_line: str, subtitle: str):
    c = Canvas(W, H, ss=SS)
    size = theme.title_size
    width = c.text_width(text_line, "title", size)
    while width > W - 260 and size > 30:
        size -= 2
        width = c.text_width(text_line, "title", size)
    y = 104
    c.text((W / 2, y + 6), text_line, "title", size, (14, 6, 24, 200), stroke=7, stroke_fill=(14, 6, 24, 200))
    c.text((W / 2, y), text_line, "title", size, Grad(theme.title_color, theme.title_color2, "v"),
           stroke=6, stroke_fill=(30, 14, 44))
    # subtitle with letter spacing
    sub = subtitle.upper()
    sub_size = 20
    spaced = " ".join(sub) if len(sub) < 30 else sub
    while c.text_width(spaced, "lilita", sub_size) > W - 220 and sub_size > 12:
        sub_size -= 1
    c.text((W / 2, y + size * 0.62 + 14), spaced, "lilita", sub_size, theme.accent, stroke=4,
           stroke_fill=(30, 14, 44))
    return c.result()


def _sprite(name: str, t: float, size: int):
    spec = EMOJIS[name]
    frame_t = t if spec.frames > 1 else 0.0
    return _cached_sprite(name, round(frame_t * spec.frames) % max(1, spec.frames), size)


@lru_cache(maxsize=512)
def _cached_sprite(name: str, frame: int, size: int):
    spec = EMOJIS[name]
    img = render_frame(name, frame / max(1, spec.frames), 128)
    img = img.resize((size, size), Image.LANCZOS)
    # dark drop shadow for depth
    sh = Image.new("RGBA", (size + 16, size + 16), (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: v * 120 // 255)
    blk = Image.new("RGBA", img.size, (8, 0, 16, 255))
    blk.putalpha(a)
    sh.alpha_composite(blk, (8, 14))
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    sh.alpha_composite(img, (8, 6))
    return sh


@lru_cache(maxsize=None)
def banner_bytes(key: str, **fmt) -> bytes:
    theme = THEMES[key]
    title = theme.title.format(**fmt)
    subtitle = theme.subtitle.format(**fmt)
    seed = sum(map(ord, key))
    sky = _sky(theme, seed % 7)
    title_layer = _title_layer(theme, title, subtitle)
    rnd = random.Random(seed)
    stars = [(rnd.uniform(10, W - 10), rnd.uniform(8, 170), rnd.uniform(1.2, 2.8), rnd.random())
             for _ in range(34)]
    sparks = [(rnd.uniform(60, W - 60), rnd.uniform(20, 150), rnd.random()) for _ in range(5)]
    frames = []
    for i in range(FRAMES):
        t = i / FRAMES
        frame = sky.copy()
        c = Canvas(W, H, ss=1)
        c.img = frame
        for (x, y, r, ph) in stars:
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin((t + ph) * math.tau))
            c.circle(x, y, r, (255, 250, 230, int(255 * a)))
        for (x, y, ph) in sparks:
            k = max(0.0, math.sin((t + ph) * math.tau))
            if k > 0.05:
                c.sparkle(x, y, 9 * k, (255, 245, 200, int(255 * k)))
        # little bat crossing the sky
        bx = (t * (W + 120)) - 60
        by = 40 + 10 * math.sin(t * math.tau * 2)
        bat = _sprite("bat", (t * 3) % 1, 34)
        frame.alpha_composite(bat, (int(bx), int(by)))
        # creatures on both sides (bobbing)
        for side, names in (("l", theme.left), ("r", theme.right)):
            for j, name in enumerate(names):
                big = j == 0
                size = 132 if big else 76
                bob = math.sin((t + j * 0.33 + (0.5 if side == "r" else 0)) * math.tau) * (6 if big else 4)
                if side == "l":
                    x = 18 if big else 120
                    y = 100 if big else 30
                else:
                    x = W - 18 - size if big else W - 140 - size // 2
                    y = 100 if big else 36
                    if name in ("star", "medal1", "gem", "potion_green", "spider", "bat", "hunter", "candy", "sparkle",
                                "tomb", "joker", "werewolf", "skull_fire", "crystal"):
                        y = 24 if not big else y
                spr = _sprite(name, t, size)
                frame.alpha_composite(spr, (int(x - 8), int(y + bob - 6)))
        frame.alpha_composite(title_layer)
        frames.append(frame)
    return banner_gif_bytes(frames, duration=100)


def banner_filename(key: str) -> str:
    return f"{key}.gif"


def prerender_all(**fmt):
    for key in THEMES:
        try:
            banner_bytes(key, **{k: v for k, v in fmt.items() if "{" + k + "}" in THEMES[key].title + THEMES[key].subtitle})
        except Exception:  # pragma: no cover - logged by caller
            raise
