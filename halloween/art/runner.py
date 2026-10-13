"""La Grande Fuite: a 2D runner. The hero flees the Reaper through the cemetery.

Every obstacle is one short clip that scrolls like a platform game: the obstacle
rushes in, the hero jumps / slides / strikes (or crashes into it), the Reaper
creeps closer after a mistake, and the clip ends on the next obstacle waiting
in the distance, so the player can react to it straight away.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .cards import _neon_layer
from .scroller import GROUND, H, W, _gif, hero, hud, place, world

HERO_X = 210
HERO_SIZE = 76
FAR_X = 590  # where the next obstacle waits on the last frame
METERS = 25  # metres run per obstacle cleared
CONTACT_X = HERO_X + 62
REAPER_X = {3: -90, 2: 40, 1: 112, 0: HERO_X - 20}  # the closer, the fewer lives left

# kind: (action that clears it, how it is drawn)
OBSTACLES = {
    "tomb": "jump", "pit": "jump", "fireskull": "jump",
    "bats": "slide", "spider": "slide", "coffin": "slide",
    "zombie": "strike", "pumpkin": "strike", "mummy": "strike",
}
CHEERS = {"jump": ["QUEL SAUT !", "HOP !", "PAR-DESSUS !"], "slide": ["GLISSADE !", "PAR-DESSOUS !", "SOUPLE !"],
          "strike": ["BAM !", "K.O. !", "DÉGAGE !"]}


# --------------------------------------------------------------------------- obstacles
@lru_cache(maxsize=64)
def _icon(name: str, size: int, color: tuple, frame: int = 0) -> Image.Image:
    return neon.icon_light(name, size, color, frame)


def _paste_center(img, sprite, x, y):
    img.alpha_composite(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)))


@lru_cache(maxsize=2)
def _pit_layer() -> Image.Image:
    """A dark hole in the ground with glowing spikes at the bottom (centred at x=60)."""
    img = Image.new("RGBA", (120, H - GROUND + 6), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((14, 0, 106, img.height), fill=(3, 1, 6, 255))
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    d.line((14, 2, 14, img.height), fill=255, width=3)
    d.line((106, 2, 106, img.height), fill=255, width=3)
    for x in range(20, 104, 14):
        d.polygon([(x, img.height), (x + 7, img.height - 22), (x + 14, img.height)], outline=255)
    img.alpha_composite(neon.glow(m, neon.RED, 3))
    return img


def draw_obstacle(img, kind: str, x: float, f: int, fly: float = 0.0, alpha: float = 1.0):
    """Draw one obstacle with its feet (or its hole) at screen x. ``fly`` > 0 sends it flying after a hit."""
    if kind == "pit":
        layer = _pit_layer()
        img.alpha_composite(layer, (round(x - 60), GROUND - 3))
        return
    if kind == "tomb":
        s = _icon("tomb", 74, neon.GREEN)
        _paste_center(img, s, x, GROUND - s.height / 2 + 8)
        return
    if kind == "fireskull":  # a burning skull rolling on the ground
        s = _icon("skull_fire", 62, neon.ORANGE).rotate(-f * 40 % 360, resample=Image.BICUBIC)
        _paste_center(img, s, x, GROUND - 28)
        return
    if kind in ("bats", "spider", "coffin"):
        line = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(line)
        if kind == "bats":
            n = max(1, neon.icon_frames("bat"))
            for i, (dx, dy) in enumerate(((-34, -126), (6, -150), (40, -118))):
                s = _icon("bat", 46, neon.PURPLE, (f + i) % n)
                _paste_center(img, s, x + dx, GROUND + dy + 6 * math.sin(f * 0.9 + i))
            return
        if kind == "spider":
            sy = GROUND - 120 + 6 * math.sin(f * 0.7)
            d.line((x, 0, x, sy - 20), fill=200, width=2)
            img.alpha_composite(neon.glow(line, neon.WHITE, 2))
            _paste_center(img, _icon("spider", 60, neon.PURPLE), x, sy)
            return
        swing = 10 * math.sin(f * 0.5)
        cy = GROUND - 118
        d.line((x - 26, 0, x - 26 + swing, cy - 14), fill=220, width=3)
        d.line((x + 26, 0, x + 26 + swing, cy - 14), fill=220, width=3)
        img.alpha_composite(neon.glow(line, neon.YELLOW, 2))
        s = _icon("coffin", 78, neon.ORANGE).rotate(90 + swing, expand=True, resample=Image.BICUBIC)
        _paste_center(img, s, x + swing, cy)
        return
    name, color, size = {"zombie": ("zombie", neon.GREEN, 92), "pumpkin": ("pumpkin_angry", neon.ORANGE, 70),
                         "mummy": ("mummy", neon.WHITE, 90)}[kind]
    s = _icon(name, size, color)
    bounce = abs(math.sin(f * 0.8)) * 16 if kind == "pumpkin" else 3 * math.sin(f * 0.6)
    y = GROUND - s.height / 2 + 6 - bounce
    if fly:
        s = s.rotate(-fly * 50, expand=True, resample=Image.BICUBIC)
        x, y = x + fly * 34, y - fly * 30 + fly * fly * 1.5
    if alpha < 1.0:
        s = neon.dim(s, alpha)
    _paste_center(img, s, x, y)


# --------------------------------------------------------------------------- overlays
def _reaper(img, x, f, color=neon.RED):
    if x < -60:
        return
    s = _icon("reaper", 108, color)
    _paste_center(img, s, x, GROUND - 76 + 8 * math.sin(f * 0.5))


def _hud(img, name: str, lives: int, dist: int, bag: int):
    hud(img, name)
    for i in range(3):
        heart = _icon("heart", 24, neon.RED if i < lives else (60, 40, 60))
        img.alpha_composite(heart, (W // 2 - 48 + i * 32, 8))
    img.alpha_composite(_neon_layer((W, H), f"{dist * METERS} M", (W // 2 + 62, 20), 16, tuple(neon.CYAN), "lm"))
    img.alpha_composite(_icon("candy", 24, neon.PINK), (W // 2 + 128, 8))
    img.alpha_composite(_neon_layer((W, H), str(bag), (W // 2 + 158, 20), 16, tuple(neon.YELLOW), "lm"))


def _warning(img, x, f):
    """A blinking '!' above the next obstacle."""
    if f % 2 == 0:
        img.alpha_composite(_neon_layer((W, H), "!", (round(x), GROUND - 176), 42, tuple(neon.YELLOW), "mm"))


def _caption(img, text, good, k=1.0):
    color = neon.GREEN if good else neon.RED
    size = int(neon.fit_text(text, 40, 460) * (0.6 + 0.4 * min(1.0, k)))
    img.alpha_composite(_neon_layer((W, H), text, (W // 2 + 40, 70), size, tuple(color), "mm"))


def _sparks(img, x, y, k, rnd_pts, color):
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for ang, v in rnd_pts:
        r = v * (k + 1)
        px, py = x + r * math.cos(ang), y + r * math.sin(ang)
        d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=tuple(color) + (max(0, 255 - 40 * k),))
    img.alpha_composite(over)


def _slash(img, x, y, k):
    """The white arc of the punch."""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).arc((x - 46, y - 46, x + 46, y + 46), -70 + 30 * k, 70 + 30 * k, fill=255, width=5)
    img.alpha_composite(neon.dim(neon.glow(m, neon.WHITE, 4), max(0.2, 1 - 0.3 * k)))


def _flash(img, color=(255, 30, 40), alpha=90):
    img.alpha_composite(Image.new("RGBA", (W, H), color + (alpha,)))


def _stars(img, x, y, f):
    for i in range(3):
        a = f * 0.9 + i * math.tau / 3
        _paste_center(img, _icon("star", 20, neon.YELLOW), x + 26 * math.cos(a), y + 8 * math.sin(a))


# --------------------------------------------------------------------------- clips
def speed(dist: int) -> float:
    return 18 + min(dist, 30) * 0.5


def _tail(frames, travel, rnd, next_kind, gap_from, gap_to, dist, bag, name, blink, f0):
    """Run on while the Reaper settles at its new distance and the next obstacle comes into view."""
    n = 11
    v = speed(dist)
    for f in range(n):
        t = (f + 1) / n
        img = world(travel)
        travel += v
        rx = REAPER_X[gap_from] + (REAPER_X[gap_to] - REAPER_X[gap_from]) * min(1.0, t * 1.4)
        _reaper(img, rx, f0 + f)
        if next_kind:
            nx = W + 90 - (W + 90 - FAR_X) * (t * t * (3 - 2 * t))
            draw_obstacle(img, next_kind, nx, f0 + f)
            if f >= n - 4:
                _warning(img, nx, f)
        if not (blink and f % 2 == 0 and f < 6):
            place(img, hero((f0 + f) % 8, HERO_SIZE), HERO_X, GROUND)
        _hud(img, name, gap_to, dist, bag)
        frames.append(img)
    return frames, travel


def step_frames(kind: str, action: str | None, ok: bool, next_kind: str | None, gap_before: int, gap_after: int,
                dist: int, bag: int, name: str = "", seed: int = 0):
    """One obstacle: it rushes in, the hero acts, the result shows, the next obstacle appears."""
    rnd = random.Random(seed)
    v = speed(dist)
    travel = rnd.uniform(0, 2000)
    frames = []
    pts = [(rnd.uniform(0, math.tau), rnd.uniform(4, 10)) for _ in range(22)]
    # A: the obstacle rushes from the distance to the hero
    n_a = 6
    for f in range(n_a):
        img = world(travel)
        travel += v
        ox = FAR_X + (CONTACT_X - FAR_X) * (f + 1) / n_a
        _reaper(img, REAPER_X[gap_before], f)
        draw_obstacle(img, kind, ox, f)
        pose = "run"
        if action and f >= n_a - 2:  # the move starts just before contact
            pose = {"jump": "jump", "slide": "slide", "strike": "strike"}[action]
        place(img, hero(f % 8, HERO_SIZE, pose), HERO_X, GROUND - (12 if pose == "jump" else 0))
        _hud(img, name, gap_before, dist, bag)
        frames.append(img)
    # B: the action itself
    n_b = 10
    hx, hy = HERO_X, 0.0
    for f in range(n_b):
        k = (f + 1) / n_b
        img = world(travel)
        _reaper(img, REAPER_X[gap_before], n_a + f)
        if ok:
            travel += v
            if action == "strike":
                draw_obstacle(img, kind, CONTACT_X, n_a + f, fly=f + 1, alpha=max(0.0, 1 - f / 8))
                place(img, hero(0, HERO_SIZE, "strike" if f < 5 else "run"), HERO_X, GROUND)
                if f < 4:
                    _slash(img, CONTACT_X - 10, GROUND - 70, f)
                _sparks(img, CONTACT_X, GROUND - 60, f, pts, neon.YELLOW)
            else:
                ox = CONTACT_X - v * (f + 1) * 1.2
                draw_obstacle(img, kind, ox, n_a + f)
                if action == "jump":
                    hy = 110 * math.sin(math.pi * k)
                    place(img, hero(0, HERO_SIZE, "jump" if k < 0.6 else "fall"), HERO_X, GROUND - hy)
                else:
                    place(img, hero(0, HERO_SIZE, "slide" if k < 0.85 else "run"), HERO_X, GROUND)
                    _sparks(img, HERO_X + 20, GROUND - 6, f % 4, pts[:8], neon.ORANGE)  # dust
            _caption(img, CHEERS[action][seed % 3], True, k * 2)
        else:
            # the obstacle crashes into the hero, who is thrown back (or falls into the pit)
            draw_obstacle(img, kind, CONTACT_X - 4 * f, n_a + f)
            if kind == "pit" and action != "jump":
                hy = -min(90, 16 * f)
                place(img, hero(0, HERO_SIZE, "fall"), CONTACT_X - 10, GROUND - hy)
            else:
                hx = HERO_X - 8 * f
                place(img, hero(0, HERO_SIZE, "hit"), hx, GROUND - (14 * math.sin(math.pi * k) if f < 5 else 0))
                _stars(img, hx, GROUND - HERO_SIZE * 1.5, f)
            if f in (0, 1):
                _flash(img)
            _caption(img, "AÏE !" if action else "TROP LENT !", False, k * 2)
        _hud(img, name, gap_before, dist, bag)
        frames.append(img)
    # C: run on towards the next obstacle
    frames, _ = _tail(frames, travel, rnd, next_kind, gap_before, gap_after, dist, bag, name, not ok, n_a + n_b)
    return frames


def _durations(frames):
    durations = [60] * len(frames)
    durations[-1] = 1500
    return durations


def step_clip(kind, action, ok, next_kind, gap_before, gap_after, dist, bag, name="", seed=0) -> bytes:
    frames = step_frames(kind, action, ok, next_kind, gap_before, gap_after, dist, bag, name, seed)
    return _gif(frames, _durations(frames))


def start_frames(first_kind: str, name: str = "", seed: int = 0):
    """The Reaper rises from a grave behind the hero, who starts running."""
    rnd = random.Random(seed)
    frames = []
    travel = rnd.uniform(0, 2000)
    for f in range(10):
        img = world(travel)
        k = (f + 1) / 10
        s = neon.dim(_icon("reaper", 108, neon.RED), k)
        _paste_center(img, s, 70, GROUND - 76 + (1 - k) * 60)
        place(img, hero(0, HERO_SIZE, "idle" if f < 6 else "hit"), HERO_X, GROUND)
        if f >= 4:
            _caption(img, "COURS !", False, (f - 3) / 3)
        _hud(img, name, 3, 0, 0)
        frames.append(img)
    frames, _ = _tail(frames, travel, rnd, first_kind, 2, 3, 0, 0, name, False, 10)
    return frames


def start_clip(first_kind: str, name: str = "", seed: int = 0) -> bytes:
    frames = start_frames(first_kind, name, seed)
    return _gif(frames, _durations(frames))
