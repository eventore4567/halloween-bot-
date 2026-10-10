"""Original CRYPT CUP application emojis.

These image bytes are created by the bot, then published once to the Discord
Developer Portal through the official application-emoji API. Rendering uses
only Pillow and stays below Discord's 256 KiB / 128x128 requirements.
No Unicode glyph, screenshot, external CDN or third-party emoji is reused.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math

from PIL import Image, ImageDraw, ImageFilter

EMOJI_NAMES = (
    "pumpkin", "ghost", "bat", "skull", "trophy",
    "key", "book", "candy", "crown", "clock",
)
SCALE = 4
SIZE = 128
P = lambda value: round(value*SCALE)

COPPER="#FFAC60"
AMBER="#FFCE7A"
VIOLET="#B88BFE"
MIST="#F1E4FF"
PURPLE="#54347D"
DARK="#24172C"
MINT="#86DDC7"

class Brush:
    def __init__(self, draw):
        self.d=draw

    def ellipse(self, b, fill, outline=None, width=3):
        self.d.ellipse([P(v) for v in b],fill=fill,outline=outline,
                       width=P(width))

    def rect(self,b,fill,outline=None,width=3,radius=0):
        b=[P(v) for v in b]
        if radius:
            self.d.rounded_rectangle(
                b,radius=P(radius),fill=fill,outline=outline,width=P(width))
        else:
            self.d.rectangle(b,fill=fill,outline=outline,width=P(width))

    def polygon(self,coords,fill,outline=None,width=3):
        coords=[(P(x),P(y)) for x,y in coords]
        self.d.polygon(coords,fill=fill)
        if outline:
            self.d.line(coords+[coords[0]],fill=outline,width=P(width),
                        joint="curve")

    def line(self,coords,fill,width=3):
        self.d.line([(P(x),P(y)) for x,y in coords],
                    fill=fill,width=P(width),joint="curve")

    def arc(self,b,start,end,fill,width=3):
        self.d.arc([P(v) for v in b],start,end,fill=fill,width=P(width))


def pumpkin(b):
    b.ellipse((18,36,110,111),fill="#E77B26",outline=DARK,width=5)
    for x in (40,67,90):
        b.arc((x-18,37,x+18,111),60,280,fill=AMBER,width=3)
    b.polygon([(58,40),(60,18),(77,14),(73,30),(67,43)],
              fill="#5FA06B",outline=DARK)
    b.polygon([(31,75),(50,58),(53,83)],fill=DARK)
    b.polygon([(76,82),(81,58),(102,76)],fill=DARK)
    b.polygon([(60,79),(68,91),(54,93)],fill=DARK)
    b.polygon([(33,93),(48,101),(57,92),(67,104),(75,92),
               (86,101),(101,92),(92,110),(42,110)],fill=DARK)


def ghost(b):
    b.polygon([(28,105),(28,58),(34,35),(48,22),(63,17),
               (81,24),(93,37),(99,54),(100,110),(86,102),
               (73,111),(60,103),(47,112)],fill=MIST,
              outline=PURPLE,width=4)
    b.ellipse((46,54,58,70),fill=DARK)
    b.ellipse((71,54,83,70),fill=DARK)
    b.ellipse((59,80,70,96),fill=PURPLE)
    b.ellipse((47,56,50,60),fill="#FFFFFF")
    b.ellipse((72,56,75,60),fill="#FFFFFF")


def bat(b):
    b.polygon([(63,55),(44,43),(33,32),(10,39),(17,66),
               (30,76),(17,89),(43,80),(55,95),(64,86),
               (73,95),(86,80),(111,90),(98,76),(112,66),
               (118,39),(95,32),(83,43),(65,55)],
              fill=PURPLE,outline=DARK,width=4)
    b.polygon([(58,48),(61,34),(66,44),(73,48),
               (73,73),(66,86),(56,74)],fill="#5C3C84")
    b.ellipse((59,55,62,59),fill=AMBER)
    b.ellipse((68,55,71,59),fill=AMBER)


def skull(b):
    b.ellipse((24,15,104,97),fill=MIST,outline=PURPLE,width=4)
    b.rect((42,78,86,109),fill=MIST,outline=PURPLE,width=3,radius=8)
    b.polygon([(35,58),(51,64),(47,81),(29,75)],fill=DARK)
    b.polygon([(93,58),(77,64),(81,81),(99,75)],fill=DARK)
    b.polygon([(61,78),(67,90),(55,89)],fill=DARK)
    for x in (50,62,74):
        b.line([(x,96),(x,108)],fill=PURPLE,width=2)


def trophy(b):
    b.polygon([(39,30),(89,30),(83,75),(72,87),(55,87),(44,75)],
              fill=AMBER,outline=DARK,width=5)
    b.arc((15,27,54,74),65,245,fill=COPPER,width=6)
    b.arc((74,27,113,74),295,110,fill=COPPER,width=6)
    b.rect((58,85,70,103),fill=COPPER)
    b.rect((40,103,88,112),fill=AMBER,outline=DARK,width=3,radius=4)
    b.polygon([(64,42),(68,51),(78,51),(70,58),
               (74,69),(64,62),(54,69),(58,58),
               (50,51),(60,51)],fill="#FDF1C6")


def key(b):
    b.ellipse((24,23,80,79),fill=PURPLE,outline=DARK,width=5)
    b.ellipse((39,37,64,62),fill=DARK)
    b.polygon([(70,64),(104,97),(100,105),(91,101),
               (86,109),(78,104),(80,95),(62,78)],
              fill=AMBER,outline=DARK,width=4)
    b.line([(71,68),(98,98)],fill="#FFF0C6",width=3)


def book(b):
    b.polygon([(15,39),(37,30),(63,39),(63,101),
               (41,92),(15,100)],fill="#F9E8CA",outline=DARK,width=4)
    b.polygon([(65,39),(91,30),(113,39),(113,100),
               (88,92),(65,101)],fill="#D9B7A6",outline=DARK,width=4)
    b.line([(64,38),(64,105)],fill=COPPER,width=3)
    for yy in (50,64,78):
        b.line([(25,yy),(51,yy-4)],fill=PURPLE,width=2)
        b.line([(78,yy-4),(103,yy)],fill=PURPLE,width=2)
    b.ellipse((56,16,72,32),fill="#EFBE70")
    b.line([(64,32),(64,38)],fill=AMBER,width=3)


def candy(b):
    b.polygon([(18,43),(39,56),(39,77),(18,91),
               (10,75),(16,66),(10,57)],fill=VIOLET,
              outline=DARK,width=3)
    b.polygon([(88,56),(110,42),(117,59),(109,66),
               (118,78),(106,90),(88,77)],fill=VIOLET,
              outline=DARK,width=3)
    b.rect((35,43,91,88),fill="#F8B0C6",outline=DARK,width=4,radius=20)
    for x in (44,59,74):
        b.line([(x,48),(x+10,83)],fill="#C75283",width=5)


def crown(b):
    b.polygon([(21,44),(40,62),(48,27),(63,60),
               (82,24),(88,61),(108,43),(101,98),
               (27,98)],fill=AMBER,outline=DARK,width=5)
    b.rect((27,94,101,110),fill=COPPER,outline=DARK,width=4,radius=4)
    for x,y in ((40,76),(63,76),(86,76)):
        b.ellipse((x-5,y-5,x+5,y+5),
                  fill=("#B77AF7" if x==63 else "#EAE3FF"))


def clock(b):
    b.rect((32,15,95,23),fill=AMBER,outline=DARK,width=3,radius=3)
    b.rect((32,104,95,112),fill=AMBER,outline=DARK,width=3,radius=3)
    b.polygon([(39,24),(89,24),(80,52),(69,63),
               (79,77),(91,103),(37,103),(49,77),
               (60,63),(47,52)],fill=MIST,outline=PURPLE,width=4)
    b.polygon([(48,42),(78,42),(69,60),(64,63),
               (59,60)],fill=COPPER)
    b.polygon([(41,98),(86,98),(72,83),(55,83)],fill=AMBER)
    b.line([(63,64),(63,79)],fill=COPPER,width=3)


_ART = {
    "pumpkin":pumpkin, "ghost":ghost, "bat":bat, "skull":skull,
    "trophy":trophy, "key":key, "book":book, "candy":candy,
    "crown":crown, "clock":clock,
}


@lru_cache(maxsize=len(EMOJI_NAMES))
def render_emoji(name: str) -> bytes:
    if name not in _ART:
        raise ValueError(f"Unknown app emoji {name!r}")
    size=SIZE*SCALE
    image=Image.new("RGBA",(size,size),(0,0,0,0))
    d=Brush(ImageDraw.Draw(image))
    _ART[name](d)
    glow=image.filter(ImageFilter.GaussianBlur(9*SCALE))
    glow.putalpha(glow.getchannel("A").point(lambda a:round(a*.35)))
    glow.alpha_composite(image)
    glow=glow.resize((SIZE,SIZE),Image.Resampling.LANCZOS)
    out=BytesIO()
    glow.save(out,format="PNG",optimize=True)
    value=out.getvalue()
    if len(value)>256*1024:
        raise ValueError(f"{name}: PNG exceeds Discord's emoji upload limit")
    return value
