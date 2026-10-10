"""The original CRYPT CUP gothic panorama.

A restrained woodcut/cathedral illustration matches the copper-framed
portal, laurel shield, and grimoire accessories in ornaments.py.
Generated once per bot process; never hot-links external imagery.
Text drawn in the image is ASCII to avoid missing decorative font glyphs.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import cos, pi, sin
from random import Random

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH = 1400
HEIGHT = 460
FILENAME = "crypt-cup-banner.jpg"
URI = f"attachment://{FILENAME}"
INK = (18, 13, 29)
PLUM = (51, 34, 60)
COPPER = (222, 161, 104)
IVORY = (245, 232, 213)
MIST = (143, 116, 148)


def _font(size: int, bold=True):
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _star(draw, x, y, radius=5, color=COPPER):
    draw.line((x-radius,y,x+radius,y),fill=color,width=2)
    draw.line((x,y-radius,x,y+radius),fill=color,width=2)


def _arch(draw, center, ground, width, height, fill, outline):
    left = center-width//2
    right=center+width//2
    roof=ground-height
    draw.rectangle((left, roof+width//2, right, ground),
                   fill=fill, outline=outline, width=3)
    draw.pieslice((left,roof,right,roof+width),180,360,
                  fill=fill,outline=outline,width=3)
    draw.rectangle((left+4,roof+width//2,right-4,ground-3),fill=fill)


def _window(draw,x,y,w=44,h=88):
    # Pointed arch with segmented, jewel-like glass.
    gold=(139,96,86)
    fill=(102,75,97)
    draw.rectangle((x,y+h//3,x+w,y+h),fill=fill)
    draw.pieslice((x,y,x+w,y+2*h//3),180,360,
                  fill=fill,outline=gold,width=3)
    draw.line((x+w//2,y+h//3,x+w//2,y+h),fill=gold,width=3)
    draw.line((x,y+2*h//3,x+w,y+2*h//3),fill=gold,width=3)
    draw.polygon([(x+w//2,y+2*h//3-6),(x+w//2+7,y+2*h//3+3),
                  (x+w//2,y+2*h//3+12),(x+w//2-7,y+2*h//3+3)],
                  fill=(207,145,90))


def _gothic_towers(draw):
    # Architectural shapes on both sides; generous empty center for title.
    dark = (13, 10, 22)
    for x in (84, 1197):
        draw.rectangle((x,280,x+85,465),fill=dark)
        draw.polygon([(x-25,281),(x+42,180),(x+110,281)],fill=dark)
        draw.line((x+42,180,x+42,155),fill=(102,70,107),width=5)
        _window(draw,x+22,310,42,83)
    draw.rectangle((0,390,245,460),fill=(14,10,24))
    draw.rectangle((1133,391,1400,460),fill=(14,10,24))
    # Arch behind the right tower.
    _arch(draw,1280,465,150,225,(26,19,40),(94,68,97))
    _window(draw,1258,276,43,96)
    for x in (30,225,1100,1370):
        draw.line((x,400,x,461),fill=(92,65,93),width=4)
        draw.arc((x-20,370,x+20,424),180,360,
                 fill=(92,65,93),width=3)


def _bats(draw):
    ink=(9,7,22)
    for x,y,size in ((286,85,1),(1009,106,.8),(1110,80,.5),
                     (337,162,.5),(1064,153,.35)):
        a=35*size
        points=[
            (x-a,y),(x-a*.66,y-15*size),(x-a*.24,y-5*size),
            (x,y+3*size),(x+a*.24,y-5*size),
            (x+a*.66,y-15*size),(x+a,y),
            (x+a*.5,y-5*size),(x+a*.25,y+10*size),
            (x,y+3*size),(x-a*.25,y+10*size),(x-a*.5,y-5*size),
        ]
        draw.polygon(points,fill=ink)


def _ornaments(draw):
    # Ornamental hairline rules, fleur-de-lis-like copper studs, and
    # internal etched corners connect to the small thumbnails.
    draw.rounded_rectangle((13,13,1387,447),radius=25,
                           outline=(131,87,119),width=4)
    draw.rounded_rectangle((24,24,1376,436),radius=19,
                           outline=(95,66,91),width=1)
    for x,y in ((49,51),(1351,51),(49,409),(1351,409)):
        draw.ellipse((x-5,y-5,x+5,y+5),fill=COPPER)
        _star(draw,x,y,14,color=(124,81,111))
    for x in (452,949):
        draw.line((x,74,x+40,74),fill=COPPER,width=2)
        draw.ellipse((x+44,71,x+50,77),fill=COPPER)
    for x in (451,949):
        draw.line((x,378,x+40,378),fill=COPPER,width=2)


def _crescent(draw, x, y, r):
    # Engraved crescent outline rather than a bright cut-out disk.
    for delta,width,color in ((0,8,COPPER),(12,3,IVORY)):
        arc=(x-r+delta,y-r,x+r+delta,y+r)
        draw.arc(arc,78,296,fill=color,width=width)


def _banner() -> Image.Image:
    picture=Image.new("RGB",(WIDTH,HEIGHT))
    pixels=picture.load()
    for y in range(HEIGHT):
        fy=y/HEIGHT
        for x in range(WIDTH):
            fx=abs(x-WIDTH/2)/(WIDTH/2)
            fog=8*max(0,1-(abs(x-710)/430))
            pixels[x,y]=(
                int(25+12*fy+12*fx+fog),
                int(17+7*fy+5*fx),
                int(37+16*fy+12*fx+fog),
            )
    art=ImageDraw.Draw(picture)
    rng=Random(72631)
    for _ in range(62):
        x=rng.randint(40,1360)
        y=rng.randint(35,240)
        size=rng.choices((1,2,3),weights=(7,3,1))[0]
        art.ellipse((x-size,y-size,x+size,y+size),
                    fill=rng.choice(((133,103,149),(176,139,155),
                                     (112,87,132))))
    _gothic_towers(art)
    _bats(art)
    _crescent(art,1085,120,54)

    # Two small pumpkins line the gate entrance. They are not copied clip-art.
    for center, yy, size in ((248,373,45),(1129,399,27)):
        art.ellipse((center-size,yy-size*.8,center+size,yy+size*.75),
                    fill=(154,76,45),outline=COPPER,width=4)
        art.arc((center-size*.54,yy-size*.8,center+size*.54,yy+size*.75),
                70,280,fill=(234,144,65),width=3)
        art.polygon([(center,yy-size*.7),(center-6,yy-10-size),
                     (center+8,yy-12-size)],
                    fill=(70,107,79))
        for shift in (-size*.36,size*.36):
            art.polygon([(center+shift-10,yy-8),(center+shift+7,yy-11),
                         (center+shift,yy+5)],fill=(32,17,35))
        art.arc((center-size*.45,yy-8,center+size*.45,yy+size*.50),
                0,180,fill=(37,18,36),width=6)

    # Center title on a mostly unobstructed field.
    title_font=_font(113,True)
    small_font=_font(26,False)
    caps_font=_font(33,True)
    title="CRYPT CUP"
    bbox=art.textbbox((0,0),title,font=title_font)
    title_x=(WIDTH-(bbox[2]-bbox[0]))//2
    art.text((title_x+4,144+5),title,font=title_font,fill=(58,30,49),
             stroke_width=5,stroke_fill=(24,14,33))
    art.text((title_x,144),title,font=title_font,fill=COPPER,
             stroke_width=2,stroke_fill=(85,52,63))
    art.text((700,96),"HALLOWEEN   /   2026",
             anchor="mm",font=small_font,fill=IVORY)
    art.line((510,125,890,125),fill=(165,111,105),width=2)
    for x in (495,905):
        _star(art,x,125,7)
    art.rounded_rectangle((407,300,993,360),radius=15,
                          fill=(33,23,43),outline=COPPER,width=3)
    art.text((700,330),"LE SANCTUAIRE DES OMBRES",anchor="mm",
             font=caps_font,fill=IVORY)
    art.text((700,391),"UN PORTAIL  /  TROIS EPREUVES  /  UN TITRE",
             anchor="mm",font=_font(22,False),
             fill=(201,171,186))
    _ornaments(art)
    return picture


@lru_cache(maxsize=1)
def banner_bytes() -> bytes:
    buffer=BytesIO()
    _banner().save(buffer,format="JPEG",quality=88,
                   optimize=True,subsampling=0)
    return buffer.getvalue()


def discord_banner() -> discord.File:
    return discord.File(BytesIO(banner_bytes()),filename=FILENAME)


def competition_files() -> list[discord.File]:
    from .ornaments import BADGES, badge_file
    return [discord_banner(),*(badge_file(name) for name in BADGES)]
