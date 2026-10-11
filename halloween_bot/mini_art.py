"""Seven original, visually distinct CRYPT CUP arcade banners (1280x310).

No reused castle, grey containers or baked-in fake buttons. Actual controls
live below these illustrations in Discord Components V2.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import random

import discord
from PIL import Image, ImageDraw

from .mini_engine import MODES
from .trick_or_treat import _write, _fit

WIDTH, HEIGHT = 1280, 310
FILENAME = "halloween-arcade.jpg"
INK=(250,237,225)
COLORS={
    "menu":((25,18,42),(110,55,108),(235,151,89)),
    "quiz":((19,31,48),(66,91,123),(140,218,234)),
    "memoire":((18,19,52),(57,61,134),(176,169,255)),
    "reflexe":((8,35,46),(34,125,128),(151,241,216)),
    "labyrinthe":((31,29,39),(88,93,84),(231,193,130)),
    "chaudron":((22,25,35),(52,101,61),(137,245,147)),
    "coffres":((46,22,32),(130,76,38),(255,190,96)),
    "des":((38,22,55),(115,47,99),(248,130,179)),
    "fantomes":((16,37,49),(44,91,104),(167,224,238)),
}


def _symbol(d,mode):
    if mode=="memoire":
        for n,x in enumerate((891,1013,1135)):
            d.rounded_rectangle((x-47,88,x+48,205),radius=16,
                                fill=(51,47,112),outline=(206,188,255),width=4)
            d.ellipse((x-22,115,x+23,164),
                      outline=(203,194,255),width=5)
            if n!=1:d.line((x-22,176,x+22,176),fill=(203,194,255),width=5)
    elif mode in ("reflexe","fantomes"):
        if mode=="fantomes":
            for x in (873,978,1090,1186):
                d.rounded_rectangle((x-26,138,x+29,219),radius=24,
                                    fill=(104,134,150),outline=(182,226,230),width=3)
                d.line((x,161,x,193),fill=(215,249,242),width=3)
        else:
            d.ellipse((945,62,1125,222),fill=(225,250,246))
            d.polygon([(948,150),(938,238),(983,209),
                       (1011,240),(1060,203),(1110,236),(1126,154)],
                      fill=(225,250,246))
            for x in (996,1072):
                d.ellipse((x-10,136,x+10,162),fill=(23,57,65))
    elif mode=="labyrinthe":
        for n,x in enumerate((879,1015,1151)):
            d.polygon([(x-59,125),(x,66),(x+59,125)],
                      fill=(32,32,46),outline=(223,188,132),width=4)
            d.rounded_rectangle((x-47,121,x+48,236),radius=18,
                                fill=(35,34,47),outline=(223,188,132),width=4)
            d.ellipse((x+15,173,x+22,180),fill=(246,202,138))
    elif mode=="chaudron":
        d.ellipse((889,91,1156,252),fill=(46,47,60),outline=(137,241,160),width=7)
        d.rectangle((909,118,1133,172),fill=(46,47,60))
        d.ellipse((904,96,1142,154),fill=(80,225,126),outline=(187,255,202),width=4)
        for x,y,r in ((934,64,14),(1025,45,21),(1113,62,12)):
            d.ellipse((x-r,y-r,x+r,y+r),fill=(162,244,155))
    elif mode=="coffres":
        d.rounded_rectangle((916,133,1142,243),radius=14,
                            fill=(136,66,36),outline=(255,193,107),width=7)
        d.arc((928,66,1130,190),180,360,fill=(255,193,107),width=11)
        d.rounded_rectangle((1004,174,1056,216),radius=10,
                            fill=(249,197,90))
        for x,y in ((934,92),(1011,71),(1101,92)):
            d.line((x-8,y,x+8,y),fill=(255,232,163),width=4)
            d.line((x,y-8,x,y+8),fill=(255,232,163),width=4)
    elif mode=="des":
        for x,y in ((913,88),(1067,122)):
            d.rounded_rectangle((x,y,x+117,y+121),radius=17,
                                fill=(234,179,216),outline=(255,220,242),width=4)
            for dx,dy in ((29,29),(87,29),(58,61),(29,92),(87,92)):
                d.ellipse((x+dx-7,y+dy-7,x+dx+7,y+dy+7),fill=(74,32,86))
    else:
        for x,y,color in ((917,118,(226,143,98)),(1045,88,(175,142,242)),
                          (1126,161,(144,226,199))):
            d.ellipse((x-29,y-29,x+29,y+29),fill=color)
            d.line((x-9,y,x+9,y),fill=(255,240,218),width=4)


@lru_cache(maxsize=10)
def banner_bytes(mode:str)->bytes:
    if mode not in COLORS:raise ValueError(mode)
    top,bottom,accent=COLORS[mode]
    im=Image.new("RGB",(WIDTH,HEIGHT),top)
    d=ImageDraw.Draw(im)
    for y in range(HEIGHT):
        fraction=y/(HEIGHT-1)
        d.line((0,y,WIDTH,y),
               fill=tuple(round(top[i]*(1-fraction)+bottom[i]*fraction)
                          for i in range(3)))
    d=ImageDraw.Draw(im)
    rnd=random.Random(len(mode)*991)
    for _ in range(55):
        x,y=rnd.randrange(35,1240),rnd.randrange(24,295)
        r=rnd.choice((1,1,2))
        d.ellipse((x-r,y-r,x+r,y+r),fill=accent)
    d.rounded_rectangle((23,18,1257,291),radius=25,
                        outline=accent,width=4)
    d.rounded_rectangle((60,45,808,256),radius=18,
                        fill=(15,13,30),outline=accent,width=3)
    title=("LE CABINET DES JEUX" if mode=="menu" else
           "LE QUIZ DES TÉNÈBRES" if mode=="quiz" else
           MODES[mode][0].upper())
    _write(im,(90,70),"CRYPT CUP / ARCADE HALLOWEEN",25,
           (218,203,223))
    _write(im,(83,121),title,_fit(title,700,size=52,min_size=32),
           accent,glow=3)
    subtitle=("SEPT MINI-JEUX, SEPT UNIVERS" if mode=="menu" else
              "QUESTIONS • QUATRE NIVEAUX" if mode=="quiz" else
              MODES[mode][1])
    _write(im,(90,211),subtitle,_fit(subtitle,690,size=22,min_size=17),INK)
    _symbol(ImageDraw.Draw(im),mode)
    io=BytesIO()
    im.save(io,"JPEG",quality=86,optimize=True)
    return io.getvalue()


def banner_file(mode:str)->discord.File:
    return discord.File(BytesIO(banner_bytes(mode)),filename=FILENAME)
