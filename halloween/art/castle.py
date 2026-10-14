"""La Hantise: the server drawn as a haunted castle.

Every category is a floor, every channel a room bearing its real name. Rooms
glow with the server's real activity, members' avatars stand in the room where
they last spoke, the Spectre haunts one room, and exorcised rooms keep a candle.
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageOps

from . import neon
from .canvas import encode_gif, png_bytes
from .cards import _neon_layer

W = 900
FLOOR_H = 118
TOP = 150  # room for the roof, the towers and the title
BOTTOM = 40
MAX_FLOORS = 6
MAX_ROOMS = 6
FLOOR_COLORS = [neon.PURPLE, neon.CYAN, neon.PINK, neon.ORANGE, neon.GREEN, neon.YELLOW]
AV = 34


@dataclass
class Room:
    cid: int
    name: str
    activity: float = 0.0  # 0..1, how lively the channel was lately
    lit: bool = False  # exorcised: a candle burns there
    people: list = field(default_factory=list)  # (uid, avatar bytes | None)


@dataclass
class Floor:
    name: str
    rooms: list[Room]
    more: int = 0  # rooms that did not fit


def clean(text: str, limit: int = 14) -> str:
    """Channel names may hold emojis the neon font cannot draw: keep letters, digits and dashes."""
    text = re.sub(r"[^0-9A-Za-zÀ-ÿ\-_ ]", "", text).strip(" -_")
    return (text or "salon")[:limit]


def height(floors: int) -> int:
    return TOP + FLOOR_H * max(1, floors) + BOTTOM


@lru_cache(maxsize=8)
def _sky(h: int) -> Image.Image:
    img = Image.new("RGBA", (W, h), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line((0, y, W, y), fill=(int(24 - 14 * t), int(8 - 4 * t), int(44 - 28 * t), 255))
    rnd = random.Random(9)
    for _ in range(110):
        x, y = rnd.randrange(W), rnd.randrange(TOP)
        v = rnd.randrange(120, 255)
        d.point((x, y), fill=(v, v, min(255, v + 30), 255))
    moon = Image.new("L", (W, h), 0)
    ImageDraw.Draw(moon).ellipse((W - 130, 18, W - 66, 82), fill=255)
    img.alpha_composite(neon.glow(moon, (255, 236, 170), 9))
    return img


def _shell(n_floors: int, h: int) -> Image.Image:
    """The castle itself: walls, battlements, two towers, the gate."""
    out = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    fill = ImageDraw.Draw(out)
    x0, x1 = 70, W - 70
    y0, y1 = TOP - 10, TOP + FLOOR_H * n_floors
    fill.rectangle((x0, y0, x1, y1), fill=(16, 9, 24, 255))
    for tx in (30, W - 110):  # towers
        fill.rectangle((tx, TOP - 70, tx + 80, y1), fill=(14, 8, 22, 255))
        fill.polygon([(tx - 8, TOP - 70), (tx + 40, TOP - 130), (tx + 88, TOP - 70)], fill=(14, 8, 22, 255))
    m = Image.new("L", (W, h), 0)
    d = ImageDraw.Draw(m)
    d.rectangle((x0, y0, x1, y1), outline=255, width=3)
    for bx in range(x0, x1, 28):  # battlements
        d.rectangle((bx, y0 - 14, bx + 14, y0), outline=255, width=2)
    for tx in (30, W - 110):
        d.rectangle((tx, TOP - 70, tx + 80, y1), outline=255, width=3)
        d.line([(tx - 8, TOP - 70), (tx + 40, TOP - 130), (tx + 88, TOP - 70)], fill=255, width=3)
        d.line((tx + 40, TOP - 130, tx + 40, TOP - 150), fill=255, width=2)
    for f in range(1, n_floors):
        y = TOP + FLOOR_H * f
        d.line((x0, y, x1, y), fill=160, width=2)
    out.alpha_composite(neon.glow(m, neon.PURPLE, 3))
    return out


def room_box(floor: int, index: int, count: int) -> tuple[int, int, int, int]:
    x0, x1 = 90, W - 90
    w = (x1 - x0) / max(1, count)
    y = TOP + FLOOR_H * floor
    return round(x0 + w * index + 6), y + 26, round(x0 + w * (index + 1) - 6), y + FLOOR_H - 8


@lru_cache(maxsize=512)
def _label(text: str, size: int, color: tuple) -> Image.Image:
    """A small neon text, drawn once on its own little canvas (much faster than a full-size layer)."""
    w = int(neon.font("neon", size).getlength(text)) + 4 * size
    h = size * 3
    return _neon_layer((w, h), text, (w // 2, h // 2), size, color, "mm")


def _put(img, label: Image.Image, x: float, y: float, anchor: str = "mm"):
    """Paste a ``_label``: centred on x, or with the text starting at x ("lm")."""
    pad = label.height * 2 / 3  # _label leaves 2 x size of margin on each side
    left = x - pad if anchor == "lm" else x - label.width / 2
    img.alpha_composite(label, (round(left), round(y - label.height / 2)))


@lru_cache(maxsize=256)
def _avatar(data: bytes | None, size: int, uid: int) -> Image.Image:
    img = None
    if data:
        try:
            img = ImageOps.fit(Image.open(BytesIO(data)).convert("RGBA"), (size, size), Image.LANCZOS)
        except Exception:  # noqa: BLE001 - a broken avatar just shows the fallback
            img = None
    disc = Image.new("L", (size, size), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, size - 1, size - 1), fill=255)
    if img is None:
        hue = FLOOR_COLORS[uid % len(FLOOR_COLORS)]
        img = Image.new("RGBA", (size, size), tuple(hue) + (255,))
        face = neon.icon_light("pumpkin_lit", int(size * 0.8), neon.WHITE)
        img.alpha_composite(face, ((size - face.width) // 2, (size - face.height) // 2))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), disc))
    ring = Image.new("L", (size + 8, size + 8), 0)
    ImageDraw.Draw(ring).ellipse((2, 2, size + 5, size + 5), outline=255, width=2)
    out = neon.glow(ring, neon.WHITE, 2)
    out.alpha_composite(img, (4, 4))
    return out


def base_map(guild_name: str, floors: list[Floor], ghost_room: int | None) -> Image.Image:
    """The castle without the moving ghost (cached by the caller for a whole animation)."""
    n = min(MAX_FLOORS, max(1, len(floors)))
    h = height(n)
    img = _sky(h).copy()
    img.alpha_composite(_shell(n, h))
    title = f"LE CHÂTEAU DE {clean(guild_name, 22).upper()}"
    img.alpha_composite(_neon_layer((W, h), title, (W // 2, 40), neon.fit_text(title, 34, W - 300),
                                    tuple(neon.ORANGE), "mm"))
    lights = Image.new("L", (W, h), 0)
    ld = ImageDraw.Draw(lights)
    outline = {}
    for f, floor in enumerate(floors[:n]):
        rooms = floor.rooms[:MAX_ROOMS]
        color = FLOOR_COLORS[f % len(FLOOR_COLORS)]
        m = outline.setdefault(color, Image.new("L", (W, h), 0))
        md = ImageDraw.Draw(m)
        label = clean(floor.name, 30).upper()
        _put(img, _label(label, 12, tuple(color)), 96, TOP + FLOOR_H * f + 13, "lm")
        for i, room in enumerate(rooms):
            box = room_box(f, i, len(rooms))
            md.rounded_rectangle(box, 8, outline=255, width=2)
            glow = int(40 + 200 * min(1.0, room.activity))
            if room.cid == ghost_room:
                glow = 20
            ld.rounded_rectangle((box[0] + 4, box[1] + 22, box[2] - 4, box[3] - 4), 6, fill=glow)
            name = "#" + clean(room.name)
            _put(img, _label(name, neon.fit_text(name, 13, box[2] - box[0] - 8), tuple(neon.WHITE)),
                 (box[0] + box[2]) / 2, box[1] + 11)
        if floor.more:
            _put(img, _label(f"+{floor.more} salons", 12, tuple(color)), W - 150, TOP + FLOOR_H * f + 13)
    warm = Image.new("RGBA", (W, h), (255, 196, 90, 0))
    warm.putalpha(lights.point(lambda v: int(v * 0.35)))
    img.alpha_composite(warm)
    for color, m in outline.items():
        img.alpha_composite(neon.glow(m, color, 3))
    # candles in exorcised rooms, members in the room where they spoke
    candle = neon.icon_light("candle", 26, neon.YELLOW)
    for f, floor in enumerate(floors[:n]):
        rooms = floor.rooms[:MAX_ROOMS]
        for i, room in enumerate(rooms):
            box = room_box(f, i, len(rooms))
            if room.lit:
                img.alpha_composite(candle, (box[2] - 26, box[3] - 30))
            people = room.people[:max(1, (box[2] - box[0] - 20) // (AV + 2))]
            for k, (uid, data) in enumerate(people):
                a = _avatar(data, AV, uid)
                img.alpha_composite(a, (box[0] + 6 + k * (AV + 2), box[3] - AV - 12))
    return img


def ghost_xy(floors: list[Floor], room_id: int | None, t: float = 1.0) -> tuple[float, float] | None:
    """Where the ghost floats: from the moon (t=0) down to its room (t=1)."""
    for f, floor in enumerate(floors[:MAX_FLOORS]):
        rooms = floor.rooms[:MAX_ROOMS]
        for i, room in enumerate(rooms):
            if room.cid == room_id:
                box = room_box(f, i, len(rooms))
                tx, ty = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2 + 6
                sx, sy = W - 98, 50
                e = t * t * (3 - 2 * t)
                return sx + (tx - sx) * e, sy + (ty - sy) * e - 60 * math.sin(math.pi * e)
    return None


def _ghost(img, xy, f, color=neon.WHITE, alpha=1.0):
    n = max(1, neon.icon_frames("ghost"))
    g = neon.icon_light("ghost", 66, color, f % n)
    if alpha < 1:
        g = neon.dim(g, alpha)
    img.alpha_composite(g, (round(xy[0] - g.width / 2), round(xy[1] - g.height / 2 + 4 * math.sin(f * 0.7))))


def map_png(guild_name: str, floors: list[Floor], ghost_room: int | None) -> bytes:
    img = base_map(guild_name, floors, ghost_room)
    xy = ghost_xy(floors, ghost_room)
    if xy:
        _ghost(img, xy, 0)
    return png_bytes(img.convert("RGB"))


def haunt_gif(guild_name: str, floors: list[Floor], ghost_room: int, caption: str) -> bytes:
    """The Spectre swoops from the moon into its room; the room goes dark."""
    base = base_map(guild_name, floors, ghost_room)
    h = base.height
    cap = _neon_layer((W, h), caption, (W // 2, 84), neon.fit_text(caption, 22, W - 260), tuple(neon.PURPLE), "mm")
    frames, durations = [], []
    for f in range(20):
        img = base.copy()
        xy = ghost_xy(floors, ghost_room, min(1.0, f / 13))
        _ghost(img, xy, f)
        if f >= 13:
            img.alpha_composite(cap)
        frames.append(img)
        durations.append(80)
    durations[-1] = 3000
    return encode_gif(frames, durations)


def exorcism_gif(guild_name: str, floors: list[Floor], room_id: int, caption: str) -> bytes:
    """The room lights up, the Spectre fades away in sparks."""
    base = base_map(guild_name, floors, None)
    h = base.height
    xy = ghost_xy(floors, room_id)
    cap = _neon_layer((W, h), caption, (W // 2, 84), neon.fit_text(caption, 22, W - 260), tuple(neon.GREEN), "mm")
    rnd = random.Random(room_id)
    sparks = [(rnd.uniform(0, math.tau), rnd.uniform(2, 6)) for _ in range(26)]
    frames, durations = [], []
    for f in range(18):
        img = base.copy()
        if xy:
            k = f / 17
            _ghost(img, (xy[0], xy[1] - 40 * k), f, neon.CYAN, max(0.0, 1 - k * 1.2))
            over = Image.new("RGBA", (W, h), (0, 0, 0, 0))
            od = ImageDraw.Draw(over)
            for ang, v in sparks:
                r = v * (f + 1) * 2
                px, py = xy[0] + r * math.cos(ang), xy[1] + r * math.sin(ang)
                od.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(255, 230, 140, max(0, 255 - 14 * f)))
            img.alpha_composite(over)
        if f >= 6:
            img.alpha_composite(cap)
        frames.append(img)
        durations.append(80)
    durations[-1] = 3000
    return encode_gif(frames, durations)
