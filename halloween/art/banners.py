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

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import neon
from .canvas import banner_gif_bytes



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
    "quiz": Theme("LE GRAND FRISSON", "LE JEU TÉLÉ · {questions} QUESTIONS", N.PINK, N.YELLOW, "skull", "crystal", N.CYAN),
    "manor": Theme("EXPÉDITIONS", "ENVOIE TES MONSTRES EN MISSION", N.PURPLE, N.GREEN, "werewolf", "chest", N.CYAN),
    "cauldron": Theme("LA FORMULE", "DÉCHIFFRE LE CODE DU CHAUDRON", N.GREEN, N.PINK, "cauldron", "potion_purple", N.PURPLE),
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
    "ouija": Theme("PLANCHE OUIJA", "L'ESPRIT ÉPELLE · TOI TU DEVINES", N.PURPLE, N.YELLOW, "crystal", "candle", N.PINK),
    "shell": Theme("BONNETEAU", "SUIS LE BONBON DES YEUX", N.ORANGE, N.PINK, "pumpkin_lit", "candy", N.PURPLE),
    "slots": Theme("MACHINE HANTÉE", "ALIGNE TROIS MONSTRES", N.PINK, N.CYAN, "gem", "crown", N.PURPLE),
    "motus": Theme("MOTUS DES OMBRES", "LE MOT EN 6 ESSAIS", N.CYAN, N.ORANGE, "book", "eye", N.GREEN),
    "hilo": Theme("PLUS OU MOINS", "LA CARTE SUIVANTE ?", N.CYAN, N.YELLOW, "star", "skull", N.PINK),
    "maze": Theme("LABYRINTHE HANTÉ", "LA CLÉ · LA PORTE · LE FANTÔME", N.PURPLE, N.CYAN, "key", "ghost", N.GREEN),
    "connect4": Theme("PUISSANCE 4 MAUDIT", "ALIGNE QUATRE CITROUILLES", N.ORANGE, N.GREEN, "pumpkin_lit", "potion_green", N.CYAN),
    "pet": Theme("FAMILIER HANTÉ", "ADOPTE · NOURRIS · FAIS ÉVOLUER", N.PINK, N.CYAN, "bat", "heart", N.PURPLE),
    "roulette": Theme("ROULETTE DES POTIONS", "UNE FIOLE SUR SIX EST EMPOISONNÉE", N.GREEN, N.PINK, "potion_green", "skull", N.YELLOW),
    "trophies": Theme("SUCCÈS", "DÉBLOQUE LES 41 TROPHÉES", N.YELLOW, N.CYAN, "trophy", "medal1", N.PURPLE),
}

W2, H2 = 760, 300
W, H = W2, H2
FLOOR = 214  # y where the wet street starts
FRAMES2 = FRAMES = 20


def _letters(text: str, size: int, cx: int, cy: int):
    """One glowing mask per letter, so letters can buzz independently."""
    f = neon.font("neon", size)
    total = f.getlength(text)
    x = cx - total / 2
    out = []
    for ch in text:
        w = f.getlength(ch)
        if ch.strip():
            m = Image.new("L", (W2, FLOOR), 0)
            ImageDraw.Draw(m).text((x, cy), ch, font=f, fill=255, anchor="lm")
            out.append(m)
        x += w
    return out


def _street(seed: int):
    """Brick wall, wet street and a drain of light under the sign."""
    img = Image.new("RGBA", (W2, H2), (8, 4, 12, 255))
    img.alpha_composite(neon.wall(W2, FLOOR, seed % 5))
    d = ImageDraw.Draw(img)
    for y in range(FLOOR, H2):
        k = (y - FLOOR) / (H2 - FLOOR)
        d.line((0, y, W2, y), fill=(14 + int(10 * k), 10 + int(6 * k), 22 + int(12 * k), 255))
    d.line((0, FLOOR, W2, FLOOR), fill=(60, 40, 70, 255), width=2)
    return img


def _reflect(layer: Image.Image, strength=0.55) -> Image.Image:
    """Upside-down, wobbly, faded copy of the sign for the wet street."""
    top = layer.crop((0, 0, W2, FLOOR))
    flip = top.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, W2, H2 - FLOOR))
    flip = flip.filter(ImageFilter.GaussianBlur(2.5))
    a = flip.getchannel("A")
    fade = Image.linear_gradient("L").resize(flip.size).transpose(Image.FLIP_TOP_BOTTOM)
    flip.putalpha(ImageChops.multiply(a, fade).point(lambda v: int(v * strength)))
    out = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    out.alpha_composite(flip, (0, FLOOR))
    return out


def banner_bytes_uncached(key: str, **fmt) -> bytes:
    theme = THEMES[key]
    title = theme.title.format(**fmt)
    subtitle = theme.subtitle.format(**fmt)
    seed = sum(map(ord, key))
    rnd = random.Random(seed)
    base = _street(seed)
    size = neon.fit_text(title, 60, W2 - 380)
    letters = [neon.glow(m, theme.color, 8) for m in _letters(title, size, W2 // 2, 82)]
    sub_size = neon.fit_text(subtitle, 22, W2 - 360)
    sub = neon.glow(neon.text_mask((W2, FLOOR), subtitle, sub_size, (W2 // 2, 146)), theme.color2, 5)
    frame = neon.glow(neon.rounded_frame_mask((W2, FLOOR), (166, 24, W2 - 166, 182), 26, 4),
                      theme.frame or theme.color2, 5)
    left_n = neon.icon_frames(theme.left)
    walker = "ghost"
    right_n = neon.icon_frames(theme.right)
    walk_n = neon.icon_frames(walker)
    eyes = [(rnd.uniform(30, 140), rnd.uniform(20, 70)), (rnd.uniform(W2 - 140, W2 - 30), rnd.uniform(20, 70))]
    rain = [(rnd.uniform(0, W2), rnd.uniform(0, H2), rnd.uniform(10, 18)) for _ in range(38)]
    flash_at = rnd.randrange(6, FRAMES2 - 3)
    buzz = [rnd.randrange(len(letters)) if letters else 0 for _ in range(FRAMES2)]
    frames = []
    for i in range(FRAMES2):
        t = i / FRAMES2
        sign = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        sign.alpha_composite(neon.dim(frame, 0.75 + 0.25 * math.sin(t * math.tau)), (0, 0))
        for k, lt in enumerate(letters):
            on = 1.0
            if k == buzz[i] and i % 3 == 0:
                on = 0.2
            if i in (flash_at + 1,):
                on = 0.45
            sign.alpha_composite(neon.dim(lt, on), (0, 0))
        sign.alpha_composite(neon.dim(sub, 0.9), (0, 0))
        # big creature on the left, gently swaying
        lf = int(t * left_n) % left_n if left_n > 1 else 0
        big = neon.icon_light(theme.left, 128, theme.color, lf)
        bob = 0 if left_n > 1 else round(4 * math.sin(t * math.tau))
        sign.alpha_composite(big, (8, 30 + bob - big.height // 8))
        rf = int(t * right_n) % right_n if right_n > 1 else 0
        right = neon.icon_light(theme.right, 112, theme.color2, rf)
        rbob = 0 if right_n > 1 else round(4 * math.sin((t + 0.5) * math.tau))
        sign.alpha_composite(right, (W2 - 150, 40 + rbob - right.height // 8))
        img = base.copy()
        if i == flash_at:  # lightning flash on the wall
            img.alpha_composite(Image.new("RGBA", (W2, FLOOR), (200, 190, 255, 45)))
        img.alpha_composite(sign)
        img.alpha_composite(_reflect(sign))
        # a monster crossing the street
        wf = int(t * walk_n * 2) % walk_n if walk_n > 1 else 0
        small = neon.icon_light(walker, 64, neon.WHITE, wf)
        x = int(-80 + (W2 + 100) * t)
        img.alpha_composite(small, (x, FLOOR - 52 + round(3 * math.sin(t * math.tau * 4))))
        # eyes blinking in the dark
        d = ImageDraw.Draw(img)
        for j, (ex, ey) in enumerate(eyes):
            if (i + j * 7) % 10 not in (0, 1):
                for dx in (0, 14):
                    d.ellipse((ex + dx - 3, ey - 2, ex + dx + 3, ey + 2), fill=(255, 220, 90, 255))
        # rain
        for (rx, ry, ln) in rain:
            y = (ry + t * H2 * 2) % H2
            x0 = (rx - y * 0.25) % W2
            d.line((x0, y, x0 - ln * 0.25, y + ln), fill=(150, 160, 210, 120), width=1)
        frames.append(img)
    return banner_gif_bytes(frames, duration=95)


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
