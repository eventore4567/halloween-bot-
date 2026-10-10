"""Compact atmospheric arcade banner in the existing CRYPT CUP art direction.

It is a wide banner, not the tiny unreadable portrait screenshot. No ALT
description is sent (Discord may render ALT as a black tag over the artwork).
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

import discord
from PIL import Image, ImageDraw

from .mini_engine import MODES
from .scene import _base, _lettering, _fit, IVORY, ORANGE, SOFT

WIDTH, HEIGHT = 1280, 310
FILENAME = "halloween-arcade.jpg"


@lru_cache(maxsize=9)
def banner_bytes(mode: str) -> bytes:
    if mode not in (*MODES, "menu"):
        raise ValueError(mode)
    base = _base().crop((0, 0, WIDTH, HEIGHT)).convert("RGBA")
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((340, 64, 938, 283), radius=30,
                        fill=(12, 8, 28, 198),
                        outline=(222, 135, 169, 176), width=3)
    base.alpha_composite(layer)
    title = "LE CABINET DES JEUX" if mode == "menu" else MODES[mode][0].upper()
    line = ("SEPT MINI-JEUX • BONBONS VIRTUELS"
            if mode == "menu" else "L'ÉPREUVE HALLOWEEN A COMMENCÉ")
    _lettering(base, (633, 121), "HALLOWEEN • CRYPT CUP",
               28, color=SOFT, anchor="mm")
    _lettering(base, (634, 180), title,
               _fit(title, 550, size=58, min_size=31),
               color=ORANGE, glow=7, anchor="mm", serif=True)
    _lettering(base, (634, 244), line, 22,
               color=IVORY, anchor="mm")
    content=BytesIO()
    base.convert("RGB").save(content, format="JPEG",
                             quality=84,optimize=True,subsampling=1)
    return content.getvalue()


def banner_file(mode: str) -> discord.File:
    return discord.File(BytesIO(banner_bytes(mode)),filename=FILENAME)
