"""La Série hantée: the opening card of each episode, starring the server's own members."""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from . import neon
from .canvas import encode_gif
from .cards import _neon_layer
from .scenes import night_bg
from .traitor import _sky, _village
from .versus import _portrait

W, H = 760, 320
PLACE_VARIANT = {"cimetiere": 0, "foret": 2, "eglise": 3, "manoir": 4}
ROLE_COLORS = [neon.CYAN, neon.ORANGE, neon.PINK]


def _background(place: str, f: int, seed: int) -> Image.Image:
    if place == "village":
        img = _sky(0.0)
        _village(img, 0.7, seed)
        return img
    return night_bg(PLACE_VARIANT.get(place, 1), f * 3).resize((W, H), Image.BILINEAR).convert("RGBA")


@lru_cache(maxsize=128)
def _text(text, x, y, size, color) -> Image.Image:
    return _neon_layer((W, H), text, (x, y), size, color, "mm")


@lru_cache(maxsize=2)
def _shade() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 110))


def episode_gif(number: int, title: str, place: str, cast: list[tuple[str, str, bytes | None]],
                ending: str | None = None, good: bool = True, seed: int = 0) -> bytes:
    """``cast``: (role label, name, avatar). ``ending``: the finale's ending title, if this is the finale."""
    rnd = random.Random(seed)
    portraits = [_portrait(av, ROLE_COLORS[i % 3], "pumpkin_lit").resize((110, 110), Image.LANCZOS)
                 for i, (_, _, av) in enumerate(cast)]
    confetti = [(rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(4, 9),
                 rnd.choice([neon.PINK, neon.YELLOW, neon.CYAN, neon.ORANGE])) for _ in range(40)]
    head = "DÉNOUEMENT" if ending else f"ÉPISODE {number}"
    big = (ending or title).upper()
    color = (neon.YELLOW if good else neon.RED) if ending else neon.ORANGE
    frames, durations = [], []
    n = 30
    for f in range(n):
        img = _background(place, f, seed)
        img.alpha_composite(_shade())
        img.alpha_composite(_text("LA SÉRIE HANTÉE", W // 2, 24, 15, tuple(neon.PURPLE)))
        k = min(1.0, f / 6)
        if f < 10:  # the title card, in the middle
            size = int(neon.fit_text(big, 40, W - 80) * (0.75 + 0.25 * k))
            img.alpha_composite(neon.dim(_text(head, W // 2, 120, 22, tuple(neon.PINK)), k))
            img.alpha_composite(neon.dim(_text(big, W // 2, 170, size, tuple(color)), k))
        else:  # it moves up, the cast slides in
            img.alpha_composite(_text(head, W // 2, 52, 16, tuple(neon.PINK)))
            img.alpha_composite(_text(big, W // 2, 84, neon.fit_text(big, 30, W - 80), tuple(color)))
            step = W / (len(portraits) + 1)
            for i, p in enumerate(portraits):
                t = min(1.0, max(0.0, (f - 10 - 3 * i) / 5))
                if t <= 0:
                    continue
                e = t * t * (3 - 2 * t)
                x = step * (i + 1)
                y = 200 + (1 - e) * 160 - 4 * math.sin(f * 0.5 + i)
                img.alpha_composite(p, (round(x - p.width / 2), round(y - p.height / 2)))
                role, name, _ = cast[i]
                img.alpha_composite(neon.dim(_text(name.upper()[:14], round(x), round(y + 66),
                                                   neon.fit_text(name.upper()[:14], 16, 180), tuple(neon.WHITE)), e))
                img.alpha_composite(neon.dim(_text(role, round(x), round(y + 86), 12,
                                                   tuple(ROLE_COLORS[i % 3])), e))
        if ending and good and f >= 12:
            over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for x, y, v, col in confetti:
                yy = (y + f * v * 8) % (H + 20) - 10
                od.rectangle((x - 3, yy - 2, x + 3, yy + 2), fill=tuple(col) + (220,))
            img.alpha_composite(over)
        frames.append(img)
        durations.append(90)
    durations[-1] = 4000
    return encode_gif(frames, durations)
