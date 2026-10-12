"""Animated neon-sign GIF banners shown at the top of every panel.

Every game gets its own sign on the same haunted brick wall: a buzzing
neon title that flickers, a second-colour subtitle, two creatures drawn
as neon line art (animated when their emoji is), a sign frame, drifting
fog and falling sparks.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import neon
from .canvas import banner_gif_bytes

W, H = 800, 250
FRAMES = 12


@dataclass(frozen=True)
class Theme:
    title: str
    subtitle: str
    color: tuple
    color2: tuple
    left: str
    right: str
    frame: tuple | None = None


N = neon
THEMES: dict[str, Theme] = {
    "hub": Theme("NUIT HANTÉE", "LE GRAND JEU D'HALLOWEEN", N.ORANGE, N.PURPLE, "pumpkin_lit", "ghost", N.PINK),
    "quiz": Theme("QUIZ MAUDIT", "{questions} QUESTIONS · 5 NIVEAUX", N.ORANGE, N.CYAN, "pumpkin_angry", "crystal", N.PURPLE),
    "manor": Theme("LE MANOIR", "RÉVEILLE TES MONSTRES", N.PURPLE, N.GREEN, "soul", "vampire", N.CYAN),
    "cauldron": Theme("L'ALCHIMISTE", "8 RECETTES SECRÈTES PAR NUIT", N.GREEN, N.PINK, "cauldron", "potion_purple", N.PURPLE),
    "wheel": Theme("ROUE DU DESTIN", "UN TOUR GRATUIT TOUTES LES 4 H", N.YELLOW, N.PINK, "wheel", "star", N.ORANGE),
    "memory": Theme("MÉMOIRE", "D'OUTRE-TOMBE · 8 PAIRES", N.CYAN, N.PURPLE, "eye", "tomb", N.GREEN),
    "hunt": Theme("CHASSE AUX FANTÔMES", "ÉVITE LA FAUCHEUSE", N.CYAN, N.RED, "ghost", "reaper", N.PURPLE),
    "duel": Theme("DUEL", "VAMPIRE · LOUP-GAROU · CHASSEUR", N.RED, N.YELLOW, "vampire", "werewolf", N.ORANGE),
    "hangman": Theme("LE PENDU", "SAUVE LE SQUELETTE", N.GREEN, N.WHITE, "skull", "spider", N.RED),
    "daily": Theme("COFFRE DU JOUR", "REVIENS CHAQUE NUIT · SÉRIE ×7", N.YELLOW, N.ORANGE, "chest", "candy_bag", N.PINK),
    "shop": Theme("BOUTIQUE", "CHEZ MORGANE LA SORCIÈRE", N.PINK, N.GREEN, "witch", "potion_gold", N.PURPLE),
    "top": Theme("PANTHÉON", "LES PLUS GRANDS MONSTRES", N.YELLOW, N.PURPLE, "trophy", "crown", N.ORANGE),
    "drop": Theme("APPARITION !", "LE PREMIER QUI CLIQUE GAGNE", N.ORANGE, N.GREEN, "gift", "bat", N.CYAN),
    "boss": Theme("ROI CITROUILLE", "TOUT LE SERVEUR CONTRE LUI", N.RED, N.ORANGE, "pumpkin_angry", "skull_fire", N.YELLOW),
    "cards": Theme("CARTES MAUDITES", "24 MONSTRES À COLLECTIONNER", N.PURPLE, N.YELLOW, "gift", "gem", N.PINK),
    "house": Theme("MAISON HANTÉE", "5 PIÈCES · 1 CRYPTE · 3 BOUGIES", N.PURPLE, N.ORANGE, "house", "door", N.GREEN),
    "race": Theme("COURSE DE BALAIS", "PARIE SUR LA BONNE SORCIÈRE", N.GREEN, N.YELLOW, "witch", "bat", N.PINK),
    "ritual": Theme("LE RITUEL", "RÉPÈTE LA FORMULE MAUDITE", N.PINK, N.CYAN, "book", "candle", N.PURPLE),
    "reflex": Theme("RÉFLEXE", "CLIQUE DÈS QU'IL APPARAÎT", N.CYAN, N.YELLOW, "ghost", "lightning", N.RED),
    "curse": Theme("MAUVAIS SORT", "VOLE LES BONBONS DES AUTRES", N.RED, N.PURPLE, "skull", "shield", N.GREEN),
    "trophies": Theme("SUCCÈS", "DÉBLOQUE LES 25 TROPHÉES", N.YELLOW, N.CYAN, "trophy", "medal1", N.PURPLE),
}

# Per-frame brightness of the title / subtitle / frame: a buzzing sign that sometimes stutters.
FLICKER = [1, 1, 0.92, 1, 1, 0.25, 1, 0.55, 1, 1, 0.95, 1]


def _scene(key: str, theme: Theme, title: str, subtitle: str):
    seed = sum(map(ord, key))
    base = neon.wall(W, H, seed % 5).copy()
    size = neon.fit_text(title, 76, W - 400)
    title_mask = neon.text_mask((W, H), title, size, (W // 2, 102))
    title_light = neon.glow(title_mask, theme.color, 9)
    sub_size = neon.fit_text(subtitle, 25, W - 420)
    sub_light = neon.glow(neon.text_mask((W, H), subtitle, sub_size, (W // 2, 168)), theme.color2, 5)
    frame_light = None
    if theme.frame:
        frame_light = neon.glow(neon.rounded_frame_mask((W, H), (182, 34, W - 182, 206), 28, 4), theme.frame, 6)
    return seed, base, title_light, sub_light, frame_light


def banner_bytes_uncached(key: str, **fmt) -> bytes:
    theme = THEMES[key]
    title = theme.title.format(**fmt)
    subtitle = theme.subtitle.format(**fmt)
    seed, base, title_light, sub_light, frame_light = _scene(key, theme, title, subtitle)
    rnd = random.Random(seed)
    shift = rnd.randrange(FRAMES)
    flicker = FLICKER[shift:] + FLICKER[:shift]
    fog = neon.fog_strip(W, 90, seed % 7)
    spark_x = rnd.uniform(W * 0.35, W * 0.65)
    sparks = [(rnd.uniform(-1.5, 1.5), rnd.uniform(0, 1)) for _ in range(7)]
    frames = []
    for i in range(FRAMES):
        t = i / FRAMES
        img = base.copy()
        f = flicker[i]
        if frame_light is not None:
            img.alpha_composite(neon.dim(frame_light, 0.4 + 0.6 * flicker[(i + 4) % FRAMES]))
        img.alpha_composite(neon.dim(sub_light, 0.85 + 0.15 * math.sin(t * math.tau)))
        img.alpha_composite(neon.dim(title_light, f))
        # creatures: animated emojis move, the others gently sway
        for name, size, (x, y), phase in ((theme.left, 150, (22, 52), 0.0), (theme.right, 128, (W - 160, 70), 0.5)):
            frames_n = neon.icon_frames(name)
            frame = int(t * frames_n) % frames_n if frames_n > 1 else 0
            light = neon.icon_light(name, size, theme.color if x < W / 2 else theme.color2, frame)
            pad = size // 4
            bob = 0 if frames_n > 1 else round(4 * math.sin((t + phase) * math.tau))
            img.alpha_composite(light, (x - pad, y - pad + bob))
        # sparks dripping from the sign when it stutters
        if f < 0.6 or flicker[i - 1] < 0.6:
            for vx, ph in sparks:
                age = (t * 3 + ph) % 1
                sx = spark_x + vx * 40 * age
                sy = 125 + 160 * age * age
                if sy < H:
                    r = 2.2 * (1 - age) + 0.6
                    dot = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
                    ImageDraw.Draw(dot).ellipse((4 - r, 4 - r, 4 + r, 4 + r), fill=(255, 236, 170, 255))
                    img.alpha_composite(dot, (int(sx) - 4, int(sy) - 4))
        # fog rolling at the bottom
        off = int(t * W)
        img.alpha_composite(fog.crop((off, 0, off + W, 90)), (0, H - 90))
        frames.append(img)
    return banner_gif_bytes(frames, duration=110)


_cache: dict[tuple, bytes] = {}


def banner_bytes(key: str, **fmt) -> bytes:
    k = (key, tuple(sorted(fmt.items())))
    if k not in _cache:
        _cache[k] = banner_bytes_uncached(key, **fmt)
    return _cache[k]


def banner_filename(key: str) -> str:
    return f"{key}.gif"


def prerender_all(**fmt):
    for key, theme in THEMES.items():
        wanted = {k: v for k, v in fmt.items() if "{" + k + "}" in theme.title + theme.subtitle}
        banner_bytes(key, **wanted)
