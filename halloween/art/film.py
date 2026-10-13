"""« Le Film de ta Nuit »: a personal animated movie (GIF) made from a player's numbers.

Seven scenes in cinemascope: studio card, title with the player's portrait,
candies counter, quiz and cards, the pet, trophies and rank, end credits.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from . import neon
from .canvas import encode_gif
from .cards import _neon_layer
from .versus import _portrait

W, H = 640, 360
BAR = 30  # letterbox


def _text(img, text, xy, size, color, max_w=560):
    size = neon.fit_text(text, size, max_w)
    img.alpha_composite(_neon_layer((W, H), text, tuple(map(int, xy)), size, tuple(color), "mm"))


def _bg(seed):
    img = neon.wall(W, H, seed % 5).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (4, 2, 8, 170)))
    return img


def _finish(img, rnd, fade=1.0):
    """Letterbox, film grain and fades."""
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rnd.randrange(W), rnd.randrange(BAR, H - BAR)
        v = rnd.randrange(60, 140)
        d.point((x, y), fill=(v, v, v, 255))
    if fade < 1:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - fade)))))
    d.rectangle((0, 0, W, BAR), fill=(0, 0, 0, 255))
    d.rectangle((0, H - BAR, W, H), fill=(0, 0, 0, 255))
    return img


def _counter(value: int, t: float) -> str:
    return f"{int(value * (1 - (1 - t) ** 3)):,}".replace(",", " ")


def film_frames(info: dict, seed: int = 0):
    rnd = random.Random(seed)
    frames, durations = [], []

    def add(img, ms=90, fade=1.0):
        frames.append(_finish(img, rnd, fade))
        durations.append(ms)

    # 1. studio card
    for k in range(6):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        _text(img, "NUIT HANTÉE PRÉSENTE", (W / 2, H / 2), 30, neon.ORANGE)
        add(img, 110 if k < 5 else 700, fade=min(1.0, (k + 1) / 4))
    # 2. title + portrait
    portrait = _portrait(info.get("avatar"), neon.CYAN, "ghost")
    for k in range(9):
        img = _bg(1)
        t = min(1.0, k / 5)
        x = round(-portrait.width + (40 + portrait.width) * (1 - (1 - t) ** 3))
        img.alpha_composite(portrait, (x, H // 2 - portrait.height // 2))
        if k >= 3:
            _text(img, "LE FILM DE LA NUIT DE", (400, 130), 20, neon.YELLOW, 360)
            _text(img, info["name"].upper(), (400, 180), 44, neon.PINK, 380)
            _text(img, f"{info['title'].upper()} · NIVEAU {info['level']}", (400, 232), 18, neon.CYAN, 380)
        add(img, 90 if k < 8 else 1300)
    # 3. candies counter with falling candies
    candy = neon.icon_light("candy", 34, neon.PINK)
    drops = [(rnd.uniform(40, W - 40), rnd.uniform(-H, 0), rnd.uniform(5, 11)) for _ in range(18)]
    for k in range(13):
        img = _bg(2)
        for x, y, v in drops:
            img.alpha_composite(candy, (int(x), int((y + k * v * 6) % (H + 40)) - 20))
        _text(img, "BONBONS GAGNÉS CETTE SAISON", (W / 2, 96), 22, neon.YELLOW)
        _text(img, _counter(info["earned"], min(1.0, k / 9)), (W / 2, 190), 86, neon.PINK)
        add(img, 85 if k < 12 else 1200)
    # 4. quiz + cards
    skull = neon.icon_light("skull", 96, neon.CYAN)
    gift = neon.icon_light("gift", 96, neon.PURPLE)
    for k in range(11):
        img = _bg(3)
        t = min(1.0, k / 7)
        img.alpha_composite(skull, (110, 92))
        img.alpha_composite(gift, (W - 110 - gift.width, 92))
        _text(img, _counter(info["quiz_right"], t), (110 + skull.width // 2, 252), 44, neon.CYAN, 240)
        _text(img, "BONNES RÉPONSES", (110 + skull.width // 2, 292), 16, neon.WHITE, 240)
        _text(img, f"{int(info['cards'] * t)}/{info['cards_total']}", (W - 110 - gift.width // 2, 252), 44,
              neon.PURPLE, 240)
        _text(img, "CARTES MAUDITES", (W - 110 - gift.width // 2, 292), 16, neon.WHITE, 240)
        add(img, 90 if k < 10 else 1200)
    # 5. the pet (or the best moment when there is none)
    pet = info.get("pet")
    for k in range(12):
        img = _bg(4)
        pulse = 1 + 0.06 * math.sin(k / 12 * math.tau * 2)
        if pet:
            size = int(150 * pulse)
            icon = neon.icon_light(pet["icon"], size, tuple(pet["color"]))
            img.alpha_composite(icon, (190 - icon.width // 2, H // 2 - icon.height // 2))
            _text(img, "TON FIDÈLE COMPAGNON", (440, 130), 20, neon.YELLOW, 340)
            _text(img, pet["name"].upper(), (440, 182), 40, tuple(pet["color"]), 340)
            _text(img, f"{pet['stage'].upper()} · NIV. {pet['level']}", (440, 230), 18, neon.CYAN, 340)
        else:
            icon = neon.icon_light("fire", int(140 * pulse), neon.ORANGE)
            img.alpha_composite(icon, (W // 2 - icon.width // 2, 70))
            _text(img, "TON PLUS BEAU MOMENT", (W / 2, 250), 20, neon.YELLOW)
            _text(img, info["best"].upper(), (W / 2, 290), 26, neon.ORANGE)
        add(img, 90 if k < 11 else 1200)
    # 6. trophies and rank
    trophy = neon.icon_light("trophy", 110, neon.YELLOW)
    crown = neon.icon_light("crown", 110, neon.ORANGE)
    for k in range(11):
        img = _bg(0)
        t = min(1.0, k / 7)
        img.alpha_composite(trophy, (120, 74))
        img.alpha_composite(crown, (W - 120 - crown.width, 74))
        _text(img, f"{int(info['achievements'] * t)}/{info['achievements_total']}", (120 + trophy.width // 2, 254),
              40, neon.YELLOW, 240)
        _text(img, "SUCCÈS", (120 + trophy.width // 2, 292), 16, neon.WHITE, 240)
        rank = f"#{info['rank']}" if info.get("rank") else "—"
        _text(img, rank, (W - 120 - crown.width // 2, 254), 44, neon.ORANGE, 240)
        _text(img, f"SUR {info['players']} JOUEURS", (W - 120 - crown.width // 2, 292), 16, neon.WHITE, 240)
        add(img, 90 if k < 10 else 1300)
    # 7. credits
    for k in range(10):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        _text(img, "FIN", (W / 2, 130), 70, neon.RED)
        _text(img, "… À SUIVRE LA NUIT PROCHAINE", (W / 2, 210), 20, neon.PURPLE)
        _text(img, "UN FILM NUIT HANTÉE · /film", (W / 2, 290 - k), 14, neon.WHITE)
        add(img, 110 if k < 9 else 2000, fade=min(1.0, (k + 1) / 4))
    return frames, durations


def _encode(frames, durations) -> bytes:
    """One palette shared by the whole movie (no flicker between scenes)."""
    return encode_gif(frames, durations, loop=0)


def film_gif(info: dict, seed: int = 0) -> tuple[bytes, float]:
    frames, durations = film_frames(info, seed)
    return _encode(frames, durations), sum(durations) / 1000
