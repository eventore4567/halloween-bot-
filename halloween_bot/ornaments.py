"""A matching set of handcrafted gothic emblems for the CRYPT CUP dashboard.

These are illustration *accessories*, not Discord emojis: the bot sends them
as small PNG attachments and shows them inside genuine Components V2 sections.
They remain usable in any guild even without uploaded application emojis.
The three crests share exactly the same copper, parchment and plum palette as
the panoramic banner.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import cos, pi, sin

import discord
from PIL import Image, ImageDraw

SIZE = 192
SCALE = 3
BADGES = ("portal", "rank", "grimoire")
BACKGROUND = "#171321"
COPPER = "#DEA168"
DARK_COPPER = "#86577A"
PARCHMENT = "#F5E8D5"
PLUM = "#382841"
GREEN = "#779D87"


def _line_points(points):
    return [(int(x * SCALE), int(y * SCALE)) for x, y in points]


def _rect(draw, box, *, fill=None, outline=None, width=1, radius=None):
    points = [int(v * SCALE) for v in box]
    if radius:
        draw.rounded_rectangle(points, radius=int(radius*SCALE),
                               fill=fill, outline=outline,
                               width=int(width*SCALE))
    else:
        draw.rectangle(points, fill=fill, outline=outline,
                       width=int(width*SCALE))


def _ell(draw, box, *, fill=None, outline=None, width=1):
    draw.ellipse([int(v*SCALE) for v in box], fill=fill, outline=outline,
                 width=int(width*SCALE))


def _line(draw, points, color=COPPER, width=2):
    draw.line(_line_points(points), fill=color, width=int(width*SCALE),
              joint="curve")


def _frame(draw):
    _rect(draw, (6,6,186,186), fill=BACKGROUND,
          outline=DARK_COPPER, width=3, radius=23)
    _rect(draw, (14,14,178,178), outline=COPPER, width=1, radius=19)
    _line(draw, [(40,30),(85,30)],color=DARK_COPPER)
    _line(draw, [(107,30),(152,30)],color=DARK_COPPER)
    _ell(draw,(92,25,100,33),fill=COPPER)
    for x,y in ((28,28),(164,28),(28,164),(164,164)):
        _ell(draw,(x-3,y-3,x+3,y+3),fill=COPPER)
    _line(draw,[(75,166),(117,166)],color=DARK_COPPER)


def _portal(draw):
    # Stone arch + iron door + an amber keyhole and moonlight.
    _ell(draw, (43,46,149,147), fill="#32243A",outline=DARK_COPPER,width=4)
    _rect(draw,(47,96,145,152),fill="#32243A")
    _rect(draw,(57,97,135,152),fill="#15111E",outline=COPPER,width=2)
    _ell(draw,(57,56,135,134),fill="#15111E",outline=COPPER,width=2)
    _rect(draw,(61,98,131,146),fill="#15111E")
    _line(draw,[(96,73),(96,145)],color=DARK_COPPER,width=2)
    for x in (73,118):
        _line(draw,[(x,101),(x,135)],color="#674F6A",width=3)
    _ell(draw,(109,114,115,120),fill=COPPER)
    _line(draw,[(111,120),(111,128)],width=2)
    for x,y in ((38,80),(145,69),(153,117)):
        _ell(draw,(x-2,y-2,x+2,y+2),fill="#ECCFA4")
    _line(draw,[(43,151),(149,151)],color=COPPER,width=3)
    _line(draw,[(55,158),(137,158)],color=DARK_COPPER,width=2)


def _rank(draw):
    # Original bronze-and-ivory shield, laurel branches and a crown.
    polygon=[(96,44),(133,62),(133,111),(125,135),(96,152),
             (67,135),(59,111),(59,62)]
    draw.polygon(_line_points(polygon),fill="#3D2940")
    draw.line(_line_points(polygon+[polygon[0]]),fill=COPPER,
              width=4*SCALE,joint="curve")
    polygon2=[(96,56),(122,68),(122,111),(116,125),(96,138),
              (76,125),(70,111),(70,68)]
    draw.line(_line_points(polygon2+[polygon2[0]]),fill="#9B6981",
              width=2*SCALE,joint="curve")
    _line(draw,[(76,97),(86,89),(96,96),(106,89),(116,97)],
          color="#F7DC9F",width=4)
    _line(draw,[(76,99),(78,111),(114,111),(116,99)],color="#F7DC9F",width=3)
    for x in (78,96,114):
        _ell(draw,(x-4,83,x+4,91),fill=COPPER)
    for direction in (-1,1):
        points=[]
        for i in range(7):
            angle=(1.22+i*0.17)
            x=96+direction*(49+6*sin(angle))
            y=139-i*12
            points.append((x,y))
            _ell(draw,(x-6,y-7,x+2,y),fill=GREEN)
        _line(draw,points,color=GREEN,width=2)
    _ell(draw,(90,145,102,157),fill=COPPER)


def _grimoire(draw):
    # Open spellbook, ornamental clasps and a small spectral flame.
    left=[(38,93),(57,82),(92,88),(95,143),(65,133),(38,139)]
    right=[(98,88),(135,82),(154,93),(154,139),(127,133),(97,143)]
    draw.polygon(_line_points(left),fill=PARCHMENT)
    draw.polygon(_line_points(right),fill="#D5B8A7")
    _line(draw,left+[left[0]],color=COPPER,width=3)
    _line(draw,right+[right[0]],color=COPPER,width=3)
    _line(draw,[(96,88),(96,145)],color="#85516B",width=3)
    for yy in (105,116,127):
        _line(draw,[(48,yy),(82,yy-4)],color="#6E5970",width=2)
        _line(draw,[(112,yy-4),(146,yy)],color="#6E5970",width=2)
    _ell(draw,(83,37,110,79),fill="#E7A15F")
    _ell(draw,(90,47,103,76),fill="#F8DDA0")
    _line(draw,[(96,84),(96,76)],color=COPPER,width=3)
    _ell(draw,(47,54,52,59),fill=COPPER)
    _ell(draw,(141,49,146,54),fill=COPPER)
    for x,y in ((62,66),(129,63)):
        _line(draw,[(x-4,y),(x+4,y)],width=1)
        _line(draw,[(x,y-4),(x,y+4)],width=1)


@lru_cache(maxsize=3)
def badge_bytes(name: str) -> bytes:
    if name not in BADGES:
        raise ValueError(f"Unknown CRYPT CUP emblem {name!r}")
    high = SIZE * SCALE
    image = Image.new("RGB",(high,high),BACKGROUND)
    draw = ImageDraw.Draw(image)
    _frame(draw)
    {"portal":_portal,"rank":_rank,"grimoire":_grimoire}[name](draw)
    image = image.resize((SIZE,SIZE), Image.Resampling.LANCZOS)
    output=BytesIO()
    image.save(output,format="PNG",optimize=True)
    return output.getvalue()


def badge_file(name: str) -> discord.File:
    return discord.File(BytesIO(badge_bytes(name)),
                        filename=f"crypt-{name}.png")


def badge_uri(name: str) -> str:
    if name not in BADGES:
        raise ValueError(name)
    return f"attachment://crypt-{name}.png"
