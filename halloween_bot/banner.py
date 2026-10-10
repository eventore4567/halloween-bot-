"""Unique CRYPT CUP panoramic artwork, generated in-memory with Pillow.

No hot-linked image, copyrighted film artwork, external CDN, API or server emoji
is required: /competition uploads its banner as a Discord message attachment.
The asset is cached in the bot process and is reproducible after every restart.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math
import random

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH = 1400
HEIGHT = 460
FILENAME = "crypt-cup-banner.jpg"
URI = f"attachment://{FILENAME}"


def _font(size: int, *, bold=True):
    candidates = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, ValueError):
            continue
    # Pillow >= 10 has a high-resolution built-in fallback, so Railway
    # does not need any system font package.
    return ImageFont.load_default(size=size)


def _bat(draw, x, y, scale=1, color=(16, 9, 33)):
    coords = [
        (-35, 0), (-24, -15), (-8, -9), (0, -5),
        (8, -9), (24, -15), (35, 0), (18, -3),
        (11, 9), (3, 2), (0, 13), (-3, 2),
        (-11, 9), (-18, -3),
    ]
    draw.polygon(
        [(x + a * scale, y + b * scale) for a, b in coords],
        fill=color,
    )


def _castle(draw):
    # Silhouette on the right edge, deliberately not covering the title.
    fill = (13, 8, 25)
    base_y = 382
    draw.polygon([
        (1020, base_y), (1050, 300), (1080, 300),
        (1100, 235), (1140, 235), (1165, 292),
        (1205, 260), (1230, 260), (1250, 210),
        (1270, 260), (1295, 260), (1300, 315),
        (1365, 275), (1400, 300), (1400, 460),
        (1020, 460),
    ], fill=fill)
    towers = [
        (1108, 240, 53, 126), (1217, 262, 46, 105),
        (1330, 279, 56, 95),
    ]
    for x, y, w, h in towers:
        draw.rectangle((x, y, x+w, y+h), fill=fill)
        draw.polygon(
            [(x-12, y), (x+w//2, y-61), (x+w+12, y)],
            fill=fill,
        )
        draw.line((x+w//2, y-60, x+w//2, y-80),
                  fill=(24, 14, 34), width=4)
        for offset in range(12, w-10, 19):
            draw.rounded_rectangle(
                (x+offset, y+35, x+offset+8, y+55),
                radius=3,
                fill=(210, 105, 46),
            )
    for x, y in ((1174, 364), (1264, 356), (1320, 373)):
        draw.arc((x-12, y-17, x+12, y+11), 180, 360,
                 fill=(227, 108, 48), width=4)


def _pumpkin(draw, x=150, y=329, width=152, height=129):
    # Custom mascot: carved jack-o'-lantern, not a stock image.
    dark = (33, 12, 28)
    orange = (249, 122, 22)
    light = (255, 191, 67)
    draw.ellipse((x-width//2, y-height//2, x+width//2, y+height//2),
                 fill=orange, outline=dark, width=7)
    for radius in (49, 25):
        draw.arc(
            (x-radius, y-height//2+2, x+radius,
             y+height//2-2),
            80, 280, fill=(170, 56, 17), width=6,
        )
        draw.arc(
            (x-radius, y-height//2+2, x+radius,
             y+height//2-2),
            -95, 95, fill=(255, 165, 44), width=3,
        )
    draw.polygon([(x-8, y-height//2+6), (x-2, y-height//2-39),
                  (x+20, y-height//2-47), (x+17, y-height//2-36),
                  (x+10, y-height//2+7)], fill=(45, 84, 46))
    draw.polygon([(x-51,y-7),(x-9,y-21),(x-30,y+17)],fill=dark)
    draw.polygon([(x+14,y-21),(x+52,y-7),(x+38,y+17)],fill=dark)
    draw.polygon(
        [(x-49,y+29),(x-21,y+41),(x-12,y+31),(x,y+42),
         (x+12,y+31),(x+21,y+41),(x+50,y+29),(x+33,y+57),
         (x-33,y+57)],
        fill=dark,
    )
    draw.line([(x-47,y+30),(x-22,y+41),(x-13,y+32)],
              fill=light,width=3)


def _banner_image() -> Image.Image:
    randomizer = random.Random(20261031)
    img = Image.new("RGB", (WIDTH,HEIGHT))
    px = img.load()
    # Purple-to-night gradient; leave center very dark for readable type.
    for y in range(HEIGHT):
        interpolation = y / HEIGHT
        for x in range(WIDTH):
            vignette = (abs(x - WIDTH/2)/(WIDTH/2)) * 0.10
            px[x,y] = (
                int(20 + 15*interpolation + vignette*45),
                int(11 + 9*interpolation + vignette*8),
                int(38 + 20*interpolation + vignette*36),
            )
    art = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    d = ImageDraw.Draw(art)

    # Moonlight bloom.
    glow = Image.new("RGBA", (WIDTH,HEIGHT), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    for radius, opacity in ((152,15),(117,21),(95,35),(76,60)):
        gd.ellipse(
            (1230-radius,102-radius,1230+radius,102+radius),
            fill=(193, 137, 242, opacity),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(27))
    art.alpha_composite(glow)
    d = ImageDraw.Draw(art)

    # Different sizes keep the starlight organic, not repeated emoji.
    for _ in range(95):
        x = randomizer.randint(28, WIDTH-25)
        y = randomizer.randint(18, 237)
        radius = randomizer.choice((1,1,1,2,2,3))
        a = randomizer.randint(55,170)
        d.ellipse((x-radius,y-radius,x+radius,y+radius),
                  fill=(221,189,255,a))
    d.ellipse((1167,42,1293,168),fill=(248,234,188,255))
    d.ellipse((1215,15,1333,153),fill=(29,15,49,255))
    for x,y,z in ((77,84,1.1),(282,132,.6),(1056,65,.8),
                  (1300,217,1.0),(331,57,.45)):
        _bat(d,x,y,z,(9,5,28,255))

    # Graveyard silhouettes to the left and distant mountains on right.
    d.polygon(
        [(0,377),(80,331),(180,348),(253,308),(330,350),
         (380,330),(445,371),(490,460),(0,460)],
        fill=(25,14,41,210),
    )
    _castle(d)
    for x,y in ((65,383),(322,401),(413,420)):
        d.rounded_rectangle((x,y-39,x+35,y+15),radius=14,
                            fill=(18,10,30,255))
        d.rectangle((x+8,y-50,x+26,y-21),fill=(18,10,30,255))
        d.rectangle((x-2,y-34,x+38,y-26),fill=(18,10,30,255))
    # Text ground and the pumpkin emblem.
    d.ellipse((46,373,271,466),fill=(10,6,19,230))
    _pumpkin(d, x=150,y=334)
    art = art.convert("RGB")
    img = Image.blend(img, art, 0.88)

    # Text halo and sharp typography.
    text_layer=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    tx=ImageDraw.Draw(text_layer)
    title_font=_font(117)
    sub_font=_font(34)
    tag_font=_font(27)
    small_font=_font(20,bold=False)
    title="CRYPT CUP"
    box=tx.textbbox((0,0),title,font=title_font,stroke_width=0)
    title_width=box[2]-box[0]
    left=352
    if title_width > 870:
        title_font=_font(104)
    left=max(317,min(370, (1050-title_width)//2 + 235))
    tx.text((left,135),title,font=title_font,
            fill=(255,153,46),stroke_width=5,stroke_fill=(48,15,33))
    halo=text_layer.filter(ImageFilter.GaussianBlur(14))
    img=Image.alpha_composite(img.convert("RGBA"),halo)
    img=Image.alpha_composite(img,text_layer)
    d=ImageDraw.Draw(img)
    d.text((405,78),"✦  HALLOWEEN 2026  ✦",font=tag_font,
           fill=(218,159,250),stroke_width=1,stroke_fill=(33,16,50))
    d.rounded_rectangle((382,291,1055,349),radius=22,
                        fill=(15,9,28,215),outline=(149,79,176),width=3)
    d.text((411,302),"LE SANCTUAIRE DES OMBRES",
           font=sub_font,fill=(247,218,251))
    d.text((405,384),"LE PORTAIL S'OUVRE  ·  LA LÉGENDE COMMENCE",
           font=small_font,fill=(207,181,222))
    d.line((344,365,1052,365),fill=(174,91,193,175),width=2)
    d.rounded_rectangle((12,12,WIDTH-13,HEIGHT-13),
                        radius=28,outline=(135,77,170),width=3)
    # Thin orange line coordinates are intentionally asymmetrical.
    d.line((15,60,15,398),fill=(248,131,37),width=5)
    return img.convert("RGB")


@lru_cache(maxsize=1)
def banner_bytes() -> bytes:
    output = BytesIO()
    _banner_image().save(
        output, format="JPEG", quality=89, optimize=True, subsampling=0,
    )
    return output.getvalue()


def discord_banner() -> discord.File:
    """Return a new upload wrapper: discord.File is not reusable."""
    return discord.File(BytesIO(banner_bytes()),filename=FILENAME)
