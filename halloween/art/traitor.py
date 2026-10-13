"""Le Traître: animated scenes of the village of Brumeval, with the players' own avatars.

``night_gif``  the village falls asleep, windows go dark, a vampire crosses the moon.
``dawn_gif``   sunrise reveals who was bitten (their portrait fades into a ghost), or who was saved.
``banish_gif`` the village banishes a suspect: torches, then their card flips to reveal the role.
``end_gif``    the winning side, every winner's portrait in a row.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageEnhance

from . import neon
from .canvas import encode_gif
from .cards import _neon_layer
from .versus import _portrait

W, H = 760, 320
GROUND = 262


# --------------------------------------------------------------------------- the village
def _sky(k_dawn: float) -> Image.Image:
    """Night sky, blending towards a purple-orange dawn as ``k_dawn`` goes 0 → 1."""
    return _sky_cached(round(k_dawn, 2)).copy()


@lru_cache(maxsize=128)
def _sky_cached(k_dawn: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        night = (int(26 - 16 * t), int(8 - 4 * t), int(46 - 30 * t))
        dawn = (int(70 + 150 * t), int(30 + 70 * t), int(90 - 40 * t))
        c = tuple(int(a + (b - a) * k_dawn) for a, b in zip(night, dawn))
        d.line((0, y, W, y), fill=c + (255,))
    return img


@lru_cache(maxsize=2)
def _stars() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(5)
    for _ in range(90):
        x, y = rnd.randrange(W), rnd.randrange(180)
        v = rnd.randrange(120, 255)
        d.point((x, y), fill=(v, v, min(255, v + 30), 255))
    return img


@lru_cache(maxsize=1)
def _houses():
    """Silhouettes of the village (filled layer, outline mask) and the window boxes."""
    fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    line = Image.new("L", (W, H), 0)
    df, dl = ImageDraw.Draw(fill), ImageDraw.Draw(line)
    rnd = random.Random(12)
    windows = []
    x = 10
    while x < W - 40:
        w = rnd.randint(70, 110)
        h = rnd.randint(60, 110)
        top = GROUND - h
        roof = [(x - 6, top), (x + w / 2, top - rnd.randint(34, 56)), (x + w + 6, top)]
        if rnd.random() < 0.15 and w > 80:  # the church and its tower
            roof = [(x + w / 2 - 16, top), (x + w / 2 - 16, top - 70), (x + w / 2, top - 104),
                    (x + w / 2 + 16, top - 70), (x + w / 2 + 16, top)]
            dl.line((x + w / 2, top - 104, x + w / 2, top - 124), fill=255, width=3)
            dl.line((x + w / 2 - 8, top - 116, x + w / 2 + 8, top - 116), fill=255, width=3)
        body = (x, top, x + w, GROUND)
        df.rectangle(body, fill=(14, 8, 22, 255))
        df.polygon(roof, fill=(14, 8, 22, 255))
        dl.rectangle(body, outline=255, width=3)
        dl.line(roof, fill=255, width=3)
        for wx in range(int(x + 12), int(x + w - 20), 30):
            for wy in range(int(top + 14), GROUND - 30, 34):
                windows.append((wx, wy, wx + 16, wy + 18))
        x += w + rnd.randint(14, 36)
    glow = neon.glow(line, neon.PURPLE, 3)
    ground = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ground).rectangle((0, GROUND, W, H), fill=(10, 5, 16, 255))
    gl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gl).line((0, GROUND, W, GROUND), fill=255, width=3)
    ground.alpha_composite(neon.glow(gl, neon.ORANGE, 3))
    return fill, glow, ground, windows


@lru_cache(maxsize=1)
def _window_light() -> Image.Image:
    """One lit window (16x18) with its glow, padded by 12 px."""
    m = Image.new("L", (40, 42), 0)
    ImageDraw.Draw(m).rectangle((12, 12, 28, 30), fill=255)
    return neon.glow(m, neon.YELLOW, 4)


def _village(img, lit: float, windows_seed=0):
    """Draw the village; ``lit`` is the share of windows still lit (0..1)."""
    fill, glow, ground, windows = _houses()
    img.alpha_composite(fill)
    order = random.Random(windows_seed).sample(range(len(windows)), len(windows))
    light = _window_light()
    for i in order[:round(len(windows) * lit)]:
        x0, y0 = windows[i][:2]
        img.alpha_composite(light, (x0 - 12, y0 - 12))
    img.alpha_composite(glow)
    img.alpha_composite(ground)


@lru_cache(maxsize=4)
def _shade(alpha: int) -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, alpha))


def _moon(img, y, color=(255, 236, 170)):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse((W - 170, y, W - 96, y + 74), fill=255)
    img.alpha_composite(neon.glow(m, color, 10))


@lru_cache(maxsize=256)
def _text(text, x, y, size, color) -> Image.Image:
    return _neon_layer((W, H), text, (x, y), size, color, "mm")


@lru_cache(maxsize=64)
def _icon(name, size, color, frame=0) -> Image.Image:
    return neon.icon_light(name, size, color, frame)


def _title(img, text, y, color, size=40, k=1.0):
    size = int(neon.fit_text(text, size, W - 80) * (0.7 + 0.3 * min(1.0, k)))
    img.alpha_composite(_text(text, W // 2, y, size, tuple(color)))


# --------------------------------------------------------------------------- scenes
def night_gif(night: int, seed: int = 0) -> bytes:
    rnd = random.Random(seed)
    frames, durations = [], []
    bat_n = max(1, neon.icon_frames("bat"))
    bats = [(rnd.uniform(-200, -40), rnd.uniform(60, 150), rnd.uniform(0.8, 1.3)) for _ in range(6)]
    n = 26
    for f in range(n):
        t = f / (n - 1)
        img = _sky(0.0)
        img.alpha_composite(_stars())
        _moon(img, 60 - 20 * t)
        # a vampire crosses the moon
        vx = -80 + (W + 160) * t
        vy = 110 - 70 * math.sin(math.pi * t)
        vamp = _icon("vampire", 70, tuple(neon.RED))
        img.alpha_composite(vamp, (round(vx - 35), round(vy - 35)))
        for bx, by, sp in bats:
            x = bx + f * 34 * sp
            if -40 < x < W + 40:
                bat = _icon("bat", 34, tuple(neon.PURPLE), (f + int(by)) % bat_n)
                img.alpha_composite(bat, (round(x), round(by + 8 * math.sin(f * 0.8 + bx))))
        _village(img, max(0.0, 1 - 1.3 * t), seed)
        _title(img, f"NUIT {night}", 42, neon.PURPLE, 44, f / 4)
        if f > 8:
            _title(img, "LE VILLAGE S'ENDORT… LES VAMPIRES SE RÉVEILLENT", 86, neon.RED, 18, (f - 8) / 4)
        frames.append(img)
        durations.append(85)
    durations[-1] = 2500
    return encode_gif(frames, durations)


def _ghostly(portrait: Image.Image, k: float) -> Image.Image:
    """The portrait loses its colours and fades as it becomes a ghost."""
    grey = ImageEnhance.Color(portrait).enhance(max(0.0, 1 - 1.5 * k))
    tint = Image.new("RGBA", grey.size, (150, 210, 255, 0))
    tint.putalpha(grey.getchannel("A").point(lambda v: int(v * 0.35 * k)))
    grey.alpha_composite(tint)
    alpha = grey.getchannel("A").point(lambda v: int(v * (1 - 0.55 * k)))
    grey.putalpha(alpha)
    return grey


def dawn_gif(name: str | None, avatar: bytes | None, saved: bool, night: int, seed: int = 0) -> bytes:
    """Sunrise over the village and the night's outcome."""
    frames, durations = [], []
    portrait = _portrait(avatar, neon.CYAN if saved else neon.RED, "ghost") if name else None
    n = 28
    for f in range(n):
        t = f / (n - 1)
        img = _sky(min(1.0, t * 1.6))
        _village(img, 0.2 + 0.5 * t, seed)
        _title(img, f"AUBE DU JOUR {night}", 36, neon.ORANGE, 34, f / 4)
        if portrait is not None and f >= 6:
            k = min(1.0, (f - 6) / 14)
            cx, cy = W // 2, 168
            if saved:
                p = portrait
                shield = _icon("shield", 64, tuple(neon.CYAN))
                img.alpha_composite(p, (cx - p.width // 2, cy - p.height // 2))
                img.alpha_composite(neon.dim(shield, min(1.0, k * 2)), (cx + 50, cy + 10))
                if f >= 12:
                    _title(img, f"{name.upper()[:18]} A ÉTÉ SAUVÉ PAR LE GARDIEN !", 292, neon.CYAN, 22,
                           (f - 12) / 4)
            else:
                p = _ghostly(portrait, k)
                y = cy - 40 * max(0.0, k - 0.3)
                img.alpha_composite(p, (cx - p.width // 2, round(y - p.height / 2)))
                if f >= 12:
                    ghost = _icon("ghost", 60, tuple(neon.WHITE))
                    img.alpha_composite(neon.dim(ghost, min(1.0, (f - 12) / 6)),
                                        (cx + 70, round(y - 80 - 10 * math.sin(f * 0.5))))
                    _title(img, f"{name.upper()[:18]} A ÉTÉ MORDU CETTE NUIT…", 292, neon.RED, 24, (f - 12) / 4)
        elif portrait is None and f >= 8:
            _title(img, "PERSONNE N'A DISPARU CETTE NUIT", 170, neon.GREEN, 30, (f - 8) / 4)
        frames.append(img)
        durations.append(85)
    durations[-1] = 3000
    return encode_gif(frames, durations)


def banish_gif(name: str, avatar: bytes | None, role_name: str, role_icon: str, guilty: bool, seed: int = 0) -> bytes:
    """Torches around the suspect, then the card flips: vampire, or an innocent."""
    frames, durations = [], []
    portrait = _portrait(avatar, neon.ORANGE, "skull")
    color = neon.RED if guilty else neon.CYAN
    fire_n = max(1, neon.icon_frames("fire"))
    card_face = _role_card(role_icon, color, portrait.size)
    n = 30
    for f in range(n):
        img = _sky(0.35)
        _village(img, 0.6, seed)
        img.alpha_composite(_shade(120))
        img.alpha_composite(_torch_sticks())
        for i, x in enumerate(TORCHES):
            fire = _icon("fire", 54, tuple(neon.ORANGE), (f + i) % fire_n)
            img.alpha_composite(fire, (x - 27, 190 - 27 + round(4 * math.sin(f * 0.7 + i))))
        cx, cy = W // 2, 160
        if f < 14:  # the suspect stands in the middle
            img.alpha_composite(portrait, (cx - portrait.width // 2, cy - portrait.height // 2))
            _title(img, f"LE VILLAGE BANNIT {name.upper()[:18]}", 36, neon.ORANGE, 30, f / 4)
        else:  # the card flips over: portrait → role
            k = min(1.0, (f - 14) / 6)
            squash = abs(math.cos(math.pi * k))
            face = portrait if k < 0.5 else card_face
            wdt = max(2, round(face.width * squash))
            card = face.resize((wdt, face.height))
            img.alpha_composite(card, (cx - wdt // 2, cy - card.height // 2))
            if k >= 1.0:
                verdict = "C'ÉTAIT UN VAMPIRE !" if guilty else f"INNOCENT… C'ÉTAIT : {role_name.upper()}"
                _title(img, verdict, 36, color, 32, (f - 20) / 4)
                if guilty:
                    _title(img, "UN DE MOINS !", 296, neon.GREEN, 22, (f - 20) / 4)
                else:
                    _title(img, "LES VAMPIRES RICANENT DANS L'OMBRE…", 296, neon.RED, 20, (f - 20) / 4)
        frames.append(img)
        durations.append(85)
    durations[-1] = 3000
    return encode_gif(frames, durations)


TORCHES = (90, 200, W - 200, W - 90)


@lru_cache(maxsize=1)
def _torch_sticks() -> Image.Image:
    stick = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(stick)
    for x in TORCHES:
        d.line((x, 212, x, 300), fill=255, width=4)
    return neon.glow(stick, neon.ORANGE, 2)


def _role_card(icon: str, color, size) -> Image.Image:
    card = Image.new("RGBA", size, (0, 0, 0, 0))
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((14, 6, size[0] - 14, size[1] - 6), 16, outline=255, width=4)
    bg = Image.new("RGBA", size, (16, 8, 24, 235))
    inner = Image.new("L", size, 0)
    ImageDraw.Draw(inner).rounded_rectangle((14, 6, size[0] - 14, size[1] - 6), 16, fill=255)
    bg.putalpha(inner)
    card.alpha_composite(bg)
    card.alpha_composite(neon.glow(m, color, 5))
    ic = neon.icon_light(icon, int(size[0] * 0.6), color)
    card.alpha_composite(ic, ((size[0] - ic.width) // 2, (size[1] - ic.height) // 2))
    return card


def end_gif(winner: str, people: list[tuple[str, bytes | None, str]], seed: int = 0) -> bytes:
    """``people``: (name, avatar, role icon) of every winner."""
    rnd = random.Random(seed)
    village = winner == "village"
    color = neon.GREEN if village else neon.RED
    title = "LE VILLAGE TRIOMPHE !" if village else "LES VAMPIRES RÈGNENT SUR BRUMEVAL"
    shown = people[:6]
    size = 96 if len(shown) <= 4 else 80
    portraits = [_portrait(av, color, icon).resize((size + 36, size + 36), Image.LANCZOS) for _, av, icon in shown]
    confetti = [(rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(4, 9),
                 rnd.choice([neon.PINK, neon.YELLOW, neon.CYAN, neon.GREEN, neon.ORANGE])) for _ in range(50)]
    frames, durations = [], []
    n = 26
    for f in range(n):
        img = _sky(1.0 if village else 0.0)
        if not village:
            img.alpha_composite(_stars())
            _moon(img, 40, (255, 90, 90))
        _village(img, 0.8 if village else 0.05, seed)
        img.alpha_composite(_shade(90))
        _title(img, title, 40, color, 38, f / 4)
        step = (W - 80) / max(1, len(portraits))
        for i, p in enumerate(portraits):
            k = min(1.0, max(0.0, (f - 3 - i * 1.5) / 4))
            if k <= 0:
                continue
            x = 40 + step * (i + 0.5)
            y = 170 + (1 - k) * 120 - 10 * abs(math.sin(f * 0.5 + i))
            img.alpha_composite(neon.dim(p, k), (round(x - p.width / 2), round(y - p.height / 2)))
            name = shown[i][0].upper()[:12]
            img.alpha_composite(_text(name, round(x), round(y + p.height / 2 + 6),
                                      neon.fit_text(name, 15, int(step) - 6), tuple(neon.WHITE)))
        if village:
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for x, y, v, col in confetti:
                yy = (y + f * v * 8) % (H + 20) - 10
                od.rectangle((x - 3, yy - 2, x + 3, yy + 2), fill=tuple(col) + (230,))
            img.alpha_composite(over)
        frames.append(img)
        durations.append(90)
    durations[-1] = 3000
    return encode_gif(frames, durations)
