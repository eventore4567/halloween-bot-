"""A single interactive /trickortreat journey, built with native Discord V2 controls.

The illustration is generated locally from Pillow; there are no remote image
dependencies, no ALT overlay and no grey Discord Container. All four screens
edit the SAME Discord message; the buttons stay native and accessible.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from functools import lru_cache
from importlib.resources import files
from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import button_icon, fail, wait_text

LOG = logging.getLogger(__name__)
WIDTH, HEIGHT = 1280, 700
NAME = "trickortreat-manoir.jpg"
URI = f"attachment://{NAME}"
CREAM = (255, 236, 214)
COPPER = (255, 169, 75)
LILAC = (204, 170, 248)
BRIGHT = (255, 208, 125)
PERIL = (248, 117, 146)
MINT = (150, 244, 189)

DOORS = (
    ("PORTE I", "Le chêne oublié", (234, 139, 57)),
    ("PORTE II", "La citrouille", (255, 181, 65)),
    ("PORTE III", "Le spectre", (154, 103, 245)),
)
RARE_NAME = "Citrouille légendaire"


@lru_cache(maxsize=64)
def _font(size, *, serif=False, bold=True):
    """Package-provided font: avoids Railway's missing-glyph/tofu fallback.

    ReportLab bundles Bitstream Vera TrueType, including accented French
    capitals, lowercase accents, bullet points and dashes. The previous
    scene renderer could use PIL's minimal fallback on Railway (rendering □).
    Never silently fall back to fonts lacking these glyphs.
    """
    family = "VeraBd.ttf" if bold or serif else "Vera.ttf"
    path = files("reportlab").joinpath("fonts", family)
    return ImageFont.truetype(str(path), size=size)


def _fit(value, width, *, size=50, min_size=24, serif=False):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for step in range(size, min_size - 1, -1):
        bounds = draw.textbbox((0, 0), str(value),
                               font=_font(step, serif=serif))
        if bounds[2] - bounds[0] <= width:
            return step
    return min_size


def _write(img, xy, value, size, color=CREAM, *, anchor=None, glow=0, serif=False):
    value = str(value)
    font = _font(size, serif=serif)
    if glow:
        shine = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shine).text(
            xy, value, font=font, anchor=anchor,
            fill=(*color, 175), stroke_width=2, stroke_fill=(*color, 110))
        img.alpha_composite(shine.filter(ImageFilter.GaussianBlur(glow)))
    ImageDraw.Draw(img).text(
        xy, value, font=font, anchor=anchor,
        fill=(*color, 255), stroke_width=1,
        stroke_fill=(12, 7, 23, 180))


def _background():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        f = y / HEIGHT
        d.line((0, y, WIDTH, y), fill=(
            int(9 + f * 24), int(12 + f * 3), int(28 + f * 13), 255
        ))
    # Moonlight and drifting mist (background only, never across labels).
    bloom = Image.new("RGBA", img.size)
    b = ImageDraw.Draw(bloom)
    b.ellipse((880, -300, 1480, 300), fill=(141, 75, 188, 83))
    b.ellipse((-160, 350, 650, 880), fill=(133, 51, 89, 70))
    img.alpha_composite(bloom.filter(ImageFilter.GaussianBlur(85)))
    d = ImageDraw.Draw(img)
    # A luminous full moon, rather than an opaque black ellipse.
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((1039, 47, 1197, 205), fill=(255, 169, 100, 115))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(27)))
    d = ImageDraw.Draw(img)
    d.ellipse((1061, 68, 1179, 186), fill=(255, 223, 178, 255))
    for x, y, radius in ((1099, 111, 12), (1141, 94, 8),
                         (1124, 156, 13), (1160, 135, 7)):
        d.ellipse((x-radius, y-radius, x+radius, y+radius),
                  fill=(230, 182, 155, 150))
    d.polygon([(0, 300), (78, 262), (115, 295), (165, 210),
               (204, 290), (238, 265), (284, 327), (330, 260),
               (378, 325), (1280, 327), (1280, 700), (0, 700)],
              fill=(13, 13, 33, 220))
    # Dark castle in the far distance.
    for x, top, height in ((970, 125, 250), (1058, 95, 280),
                           (1145, 164, 215)):
        d.rectangle((x, top + 58, x + 46, height + 157),
                    fill=(14, 11, 31))
        d.polygon([(x-17, top+59), (x+22, top), (x+63, top+59)],
                  fill=(14, 11, 31))
        d.rectangle((x+15, top+88, x+25, top+111), fill=(224, 116, 55))
    rnd = random.Random(1031)
    for _ in range(75):
        x, y = rnd.randint(25, 1240), rnd.randint(18, 310)
        if 450 < x < 870 and y > 140:
            continue
        r = rnd.choice((1, 1, 2))
        d.ellipse((x-r, y-r, x+r, y+r), fill=(222, 164, 227, 170))
    d.rounded_rectangle((20, 18, 1260, 682), radius=26,
                        outline=(226, 120, 80, 165), width=3)
    return img


def _door(img, center, *, number, chosen=False):
    x = center
    y = 354
    _, caption, hue = DOORS[number]
    d = ImageDraw.Draw(img)
    # Carved arch: a pointed roof plus a glowing wooden entrance.
    frame = (x-126, y-75, x+126, y+200)
    if chosen:
        halo = Image.new("RGBA", img.size)
        h = ImageDraw.Draw(halo)
        h.ellipse((x-167, y-85, x+167, y+290), fill=(*hue, 105))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(35)))
        d = ImageDraw.Draw(img)
    d.rounded_rectangle(frame, radius=42,
                        fill=(39, 21, 37, 255),
                        outline=(*hue, 255), width=9 if chosen else 5)
    d.polygon([(x-124,y+32), (x,y-125), (x+124,y+32)],
              fill=(28, 18, 36), outline=(*hue,255), width=6)
    d.rounded_rectangle((x-96, y-32, x+96, y+175), radius=23,
                        fill=(64, 29, 26) if number!=2 else (39, 26, 78),
                        outline=(*hue, 225), width=3)
    d.line((x,y-26,x,y+169),fill=(*hue,110),width=3)
    for yy in (y+17,y+60,y+108,y+153):
        d.line((x-85,yy,x+85,yy),fill=(*hue,45),width=2)
    d.ellipse((x+47,y+90,x+64,y+107),fill=BRIGHT)
    d.ellipse((x+52,y+95,x+59,y+102),fill=(66,38,38))
    for dx in (-89,89):
        d.ellipse((x+dx-5,y+153,x+dx+5,y+164),fill=(*hue,255))
    # Keep door captions clear of the bottom status bar (starts at y=614).
    _write(img, (x, y+183), f"PORTE {number+1}", 31,
           COPPER if chosen else CREAM, anchor="mm")
    _write(img, (x, y+225), caption, 21, LILAC, anchor="mm")


def _header(img, title, kicker):
    """Three separate text baselines, all within one compact header."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 49, 876, 217), radius=24,
                        fill=(15, 10, 30, 233),
                        outline=(202, 123, 91, 175), width=3)
    _write(img, (92, 69), "CRYPT CUP    /    HALLOWEEN", 22, LILAC)
    _write(img, (93, 105), kicker, 20, CREAM)
    size = _fit(title, 725, size=61, min_size=37, serif=True)
    _write(img, (89, 137), title, size, COPPER, glow=4, serif=True)


def _status(img, candies, streak, *, extra="CHOISIS UNE PORTE"):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((54, 614, 1225, 661), radius=12,
                        fill=(18, 13, 36, 243),
                        outline=(192, 108, 93, 120), width=2)
    for x in (441, 821):
        d.line((x, 625, x, 650), fill=(196, 116, 115, 135), width=2)
    _write(img, (81, 624), f"SAC   {candies:,} BONBONS".replace(",", " "),
           22, BRIGHT)
    label = "VICTOIRE" if streak == 1 else "VICTOIRES"
    _write(img, (467, 624), f"SÉRIE   {streak} {label}", 22, CREAM)
    _write(img, (841, 624), extra, 21, LILAC)


def _information(img, title, lines, *, selected=None, hue=COPPER):
    _header(img, title, "LE MANOIR GARDE SES SECRETS")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((71, 239, 1205, 580), radius=22,
                        fill=(19, 12, 33, 239), outline=(*hue, 165), width=3)
    visible = [str(line) for line in lines if line][:6] or ["AUCUNE INFORMATION"]
    slot = 318 // len(visible)
    height = min(58, slot - 6)
    for j, label in enumerate(visible):
        y = 251 + j * slot + (slot - height) // 2
        d.rounded_rectangle((94, y, 1183, y+height), radius=12,
                            fill=(36, 23, 49, 230),
                            outline=(*hue, 90), width=2)
        d.rounded_rectangle((96, y+8, 102, y+height-8), radius=3,
                            fill=(*hue, 255))
        font = _fit(label, 1010, size=36 if j == 0 else 31,
                    min_size=23)
        _write(img, (122, y+max(5, (height-font)//3)), label, font,
               hue if j == 0 else CREAM)


def _leaderboard(img, leaders):
    """Five balanced rows, including reserved places when fewer users play."""
    _header(img, "LES LÉGENDES", "TOP 5 DES CHASSEURS DU SERVEUR")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((71, 240, 1205, 583), radius=23,
                        fill=(15, 10, 31, 242),
                        outline=(250, 185, 113, 179), width=3)
    medals = ((255, 189, 88), (187, 196, 221), (210, 137, 96),
              (150, 128, 192), (150, 128, 192))
    for i in range(5):
        y = 256 + i * 63
        filled = i < len(leaders)
        tone = medals[i]
        d.rounded_rectangle((93, y, 1183, y+56), radius=15,
                            fill=(48, 28, 52, 239) if i == 0 and filled
                            else (32, 22, 46, 226),
                            outline=(*tone, 200) if filled else
                            (104, 84, 117, 90), width=2)
        d.ellipse((112, y+7, 153, y+48),
                  fill=(53, 38, 57, 255),
                  outline=(*tone, 240) if filled else (95, 80, 111, 170),
                  width=3)
        _write(img, (121, y+15), f"{i+1:02}", 21,
               tone if filled else LILAC)
        if filled:
            _, name, score = leaders[i]
            label = str(name).strip()[:28] or f"Chasseur #{i+1}"
            amount = f"{score:,}".replace(",", " ") + " BONBONS"
        else:
            label = "PLACE À PRENDRE"
            amount = "—"
        font = _fit(label, 590, size=31, min_size=22)
        _write(img, (185, y+12), label, font,
               CREAM if filled else (149, 136, 169))
        _write(img, (1152, y+16), amount, 25 if filled else 31,
               BRIGHT if filled else (149, 136, 169), anchor="ra")


def _sweet(draw, x, y, size, color):
    """A wrapped caramel — deterministic Pillow artwork, no external images."""
    r=size
    draw.polygon([(x-r-18,y-r//2),(x-r+2,y-r//3),
                  (x-r+1,y+r//3),(x-r-18,y+r//2)],
                 fill=(*color,220))
    draw.polygon([(x+r+18,y-r//2),(x+r-2,y-r//3),
                  (x+r-1,y+r//3),(x+r+18,y+r//2)],
                 fill=(*color,210))
    draw.ellipse((x-r,y-r//2,x+r,y+r//2),
                 fill=(*color,255),outline=(255,222,170,215),width=2)
    draw.arc((x-r+4,y-r//2+2,x+r-6,y+r//2-3),
             195,275,fill=(255,242,209,190),width=3)


def _visual_prize(img, kind):
    """Draw one distinctive, full-sized visual outcome on the left."""
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((93,258,544,564),radius=21,
                        fill=(24,16,40,248),
                        outline=(179,110,116,160),width=2)
    spotlight={
        "treat": (125,228,155),
        "jackpot": (254,174,73),
        "trick": (184,110,222),
        "nothing": (124,123,176),
    }[kind]
    glow=Image.new("RGBA",img.size,(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    gd.ellipse((146,260,506,559),fill=(*spotlight,94))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(44)))
    d=ImageDraw.Draw(img)
    d.ellipse((159,519,485,547), fill=(10,8,21,230))
    if kind in ("treat","jackpot"):
        # Antique chest with a real illustrated lid, straps, and candy loot.
        d.rounded_rectangle((181,373,475,465),radius=21,
                            fill=(83,42,32,255),
                            outline=(248,181,86,255),width=7)
        d.arc((194,341,464,431),183,355,fill=(245,181,87,255),width=10)
        d.rounded_rectangle((193,394,463,460),radius=12,
                            fill=(29,17,28,255),outline=(254,190,91,255),width=4)
        rng=random.Random(54 if kind=="treat" else 93)
        shades=((243,140,72),(162,111,240),(117,208,171),(241,105,163),
                (250,210,99))
        # Sweets break the flat rectangle; randomized positions are fixed.
        for i in range(18 if kind=="jackpot" else 13):
            x=rng.randint(221,444)
            y=rng.randint(354,418)
            _sweet(d,x,y,rng.randint(8,13),shades[i%len(shades)])
        d.rounded_rectangle((171,439,483,531),radius=13,
                            fill=(114,56,37,255),
                            outline=(255,193,103,255),width=7)
        for x in (225,419):
            d.rounded_rectangle((x,445,x+18,524),radius=4,
                                fill=(238,155,76,255))
        d.rounded_rectangle((315,458,350,495),radius=6,
                            fill=(254,202,106),outline=(115,65,37),width=4)
        d.ellipse((330,464,339,477),fill=(88,44,29))
        if kind=="jackpot":
            # Legendary pumpkin aura rising out of the chest.
            d.ellipse((283,267,375,353), fill=(252,179,76,255),
                      outline=(255,235,139,255),width=4)
            d.rectangle((322,257,338,274),fill=(83,141,83))
            d.polygon([(305,293),(321,314),(294,312)],fill=(59,36,34))
            d.polygon([(350,293),(337,314),(362,312)],fill=(59,36,34))
            d.arc((306,307,353,341),4,177,fill=(59,36,34),width=6)
        for (x,y) in ((203,316),(445,322),(368,287),(254,298)):
            d.line((x-8,y,x+8,y),fill=(255,223,149,210),width=3)
            d.line((x,y-8,x,y+8),fill=(255,223,149,210),width=3)
    elif kind=="trick":
        # Ghost with tapered wavy silhouette and expressive eyes.
        d.ellipse((218,299,428,495),fill=(226,216,255,244))
        d.polygon([(224,383),(218,481),(249,466),(285,498),(319,465),
                   (353,505),(393,468),(430,493),(428,380)],
                  fill=(226,216,255,244))
        d.ellipse((270,379,297,418),fill=(31,19,53,255))
        d.ellipse((350,379,377,418),fill=(31,19,53,255))
        d.ellipse((309,431,340,455),fill=(53,31,79,255))
        for x,y in ((170,323),(476,344),(199,493),(449,477)):
            _sweet(d,x,y,9,(221,97,166))
    else:
        # Empty tomb and cobweb, no treasure.
        d.rounded_rectangle((206,344,430,517),radius=25,
                            fill=(77,72,104,255),
                            outline=(156,139,176,235),width=7)
        d.arc((201,301,438,404),180,360,
              fill=(173,156,186,255),width=7)
        _write(img,(318,407),"VIDE",44,LILAC,anchor="mm")
        d.line((263,477,380,477),fill=(128,118,148,180),width=3)
        for radius in (45,77,104):
            d.arc((369-radius,280-radius//2,369+radius,280+radius),
                  10,170,fill=(192,179,211,170),width=2)
        for ex,ey in ((405,302),(457,357),(467,408)):
            d.line((369,280,ex,ey),fill=(192,179,211,145),width=2)


def _result_scene(img, result, remaining):
    """Outcome-specific illustration beside a genuinely readable status panel."""
    kind=result["kind"]
    palette={
        "treat":("BONBONS DÉCOUVERTS","Le manoir t'offre des friandises.",MINT),
        "jackpot":("TRÉSOR LÉGENDAIRE","Une citrouille rare surgit du coffre !",BRIGHT),
        "trick":("LE FANTÔME ATTAQUE","Un spectre emporte tes bonbons...",PERIL),
        "nothing":("LE MANOIR EST VIDE","Les ombres cachent un coffre vide.",LILAC),
    }
    title,story,color=palette[kind]
    _header(img,title,"LE VERDICT DE LA PORTE")
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((70,238,1205,586),radius=22,
                        fill=(16,11,31,235),
                        outline=(*color,200),width=3)
    _visual_prize(img,kind)
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((559,258,1184,565),radius=20,
                        fill=(31,20,43,249),
                        outline=(*color,155),width=2)
    _write(img,(583,281),"RÉCOMPENSE DU MANOIR",22,LILAC)
    amount=result["amount"]
    amount_str=(f"+{amount:,}" if amount>0 else str(amount)).replace(","," ")
    _write(img,(581,321),f"{amount_str} BONBONS",
           _fit(f"{amount_str} BONBONS",580,size=52,min_size=33),
           color,glow=3)
    d.line((589,397,1151,397),fill=(*color,140),width=2)
    _write(img,(588,418),story,
           _fit(story,550,size=25,min_size=19),CREAM)
    if result.get("rare"):
        note="OBJET REÇU : CITROUILLE LÉGENDAIRE"
    elif amount>0:
        note="BUTIN AJOUTÉ À TON SAC"
    elif amount<0:
        note="LES BONBONS RESTANTS SONT PROTÉGÉS"
    else:
        note="AUCUNE PERTE DE BONBONS"
    d.rounded_rectangle((584,471,1155,512),radius=10,
                        fill=(40,29,55,255),outline=(*color,125),width=2)
    _write(img,(602,477),note,_fit(note,528,size=21,min_size=17),BRIGHT)
    wait_note=(f"NOUVELLE PARTIE DANS {(remaining+59)//60} MIN"
               if remaining else "UNE NOUVELLE PARTIE EST DISPONIBLE")
    _write(img,(587,529),wait_note,_fit(wait_note,550,size=19,min_size=16),
           LILAC)


def _inventory(img, items):
    """Six genuine collectible slots, displaying existing items only."""
    from .content import ITEMS
    _header(img,"LE SAC DU CHASSEUR","COLLECTION ET RARETÉS")
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((71,239,1205,580),radius=23,
                        fill=(17,11,32,242),
                        outline=(240,161,90,195),width=3)
    # Each row derives from SQLite inventory; catalogue slots are previews
    # only. They DO NOT confer an item, nor claim anything new is obtainable.
    records={}
    for item in items:
        if len(item)==3:
            key,name,qty=item
        else:
            name,qty=item
            key=next((k for k,(title,*_) in ITEMS.items()
                      if title.split(" ",1)[-1]==name),name)
        if qty>0:
            records[str(key)]=(str(name),int(qty))
    catalogue={
        "legendary_pumpkin":"Citrouille légendaire",
        **{key:label.split(" ",1)[-1] for key,(label,*_) in ITEMS.items()}
    }
    showcased=list(records)
    for key in catalogue:
        if key not in records:
            showcased.append(key)
    grades={
        "legendary_pumpkin":("LÉGENDAIRE",(244,183,74)),
        "crown":("ÉPIQUE",(190,143,239)),
        "cape":("RARE",(146,176,240)),
        "lantern":("RARE",(146,176,240)),
        "ring":("RARE",(146,176,240)),
        "broom":("RARE",(146,176,240)),
    }
    for i,key in enumerate(showcased[:6]):
        col,row=i%2,i//2
        x=97+col*358
        y=325+row*74
        name,qty=records.get(key,(catalogue.get(key,str(key)),0))
        grade,tone=grades.get(key,("COMMUN",(208,176,137)))
        d.rounded_rectangle((x,y,x+343,y+64),radius=13,
                            fill=(43,27,52,246) if qty else (28,22,43,235),
                            outline=(*tone,190) if qty else (93,77,110,115),
                            width=2)
        d.rounded_rectangle((x+8,y+12,x+13,y+51),radius=2,
                            fill=(*tone,255) if qty else (94,82,113,255))
        short=name[:21]
        _write(img,(x+29,y+8),short,
               _fit(short,248,size=23,min_size=18),
               CREAM if qty else (164,151,181))
        _write(img,(x+30,y+38),
               grade if qty else "NON POSSÉDÉ",15,
               tone if qty else (126,115,146))
        _write(img,(x+322,y+35),f"×{qty}" if qty else "—",
               20,BRIGHT if qty else (122,110,145),anchor="ra")

    d.rounded_rectangle((816,260,1173,555),radius=20,
                        fill=(40,24,44,240),
                        outline=(229,151,98,145),width=3)
    # An original glowing pumpkin keeps the visual identity consistent.
    glow=Image.new("RGBA",img.size)
    ImageDraw.Draw(glow).ellipse((849,280,1130,492),fill=(245,143,66,80))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
    d=ImageDraw.Draw(img)
    d.ellipse((864,303,1126,496),fill=(193,82,31,255))
    d.ellipse((898,306,1094,495),fill=(236,117,40,255))
    d.ellipse((942,309,1051,493),fill=(255,155,69,255))
    d.polygon([(989,309),(977,272),(998,262),(1014,311)],
              fill=(77,141,77,255))
    d.polygon([(940,367),(969,407),(921,407)],fill=(46,25,35,255))
    d.polygon([(1050,366),(1023,407),(1074,408)],fill=(46,25,35,255))
    d.arc((933,399,1062,473),3,179,fill=(46,25,35,255),width=13)
    completed=sum(1 for key in catalogue if key in records)
    total=len(catalogue)
    _write(img,(996,514),f"{completed} / {total} OBJETS",
           22,BRIGHT,anchor="mm")
    # Progress line conveys collection completion without making up prizes.
    d.rounded_rectangle((880,540,1118,548),radius=4,fill=(67,48,71))
    d.rounded_rectangle((880,540,
                         881+round(237*completed/total),548),
                        radius=4,fill=(*COPPER,255))


def banner_bytes(stage, candies, streak, *, selected=None, result=None,
                 inventory=(), leaders=(), remaining=0):
    img = _background()
    if stage == "intro":
        _header(img, "LE MANOIR HANTÉ", "TROIS PORTES • UN SEUL DESTIN")
        _door(img, 249, number=0)
        _door(img, 640, number=1)
        _door(img, 1030, number=2)
        _status(img, candies, streak,
                extra=(f"RETOUR DANS {(remaining+59)//60} MIN"
                       if remaining else "CHOISIS UNE PORTE"))
    elif stage == "opening":
        _header(img, "LA PORTE S'OUVRE...", "UN BRUIT ETRANGE RESONNE DANS L'OMBRE")
        _door(img, 640, number=selected or 0, chosen=True)
        _write(img,(235,477),"QU'Y A-T-IL DERRIERE ?", 34, BRIGHT)
        _status(img, candies, streak, extra="REVELATION...")
    elif stage == "result" and result:
        _result_scene(img,result,remaining)
        _status(img,result["candies"],result["streak"],
                extra=f"PORTE {(selected or 0)+1}")
    elif stage=="inventory":
        _inventory(img, inventory)
        _status(img,candies,streak,extra="INVENTAIRE")
    elif stage=="leaderboard":
        _leaderboard(img, leaders[:5])
        _status(img,candies,streak,extra="CLASSEMENT")
    else:
        _information(img,"PORTES REFERMEES",
                     ["LA NUIT A REPRIS SES DROITS",
                      "RELANCE /TRICKORTREAT POUR JOUER"])
        _status(img,candies,streak,extra="EXPIRE")
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85,
                            optimize=True, subsampling=1)
    return buf.getvalue()


def banner_file(stage, candies, streak, **kwargs):
    return discord.File(BytesIO(banner_bytes(stage,candies,streak,**kwargs)),
                        filename=NAME)


def _gallery():
    # Deliberately no description: some Discord clients draw ALT overlays.
    return discord.ui.MediaGallery(discord.MediaGalleryItem(media=URI))


class TrickOrTreatView(discord.ui.LayoutView):
    def __init__(self, bot, guild_id, owner_id):
        super().__init__(timeout=180)
        self.bot=bot
        self.guild_id=guild_id
        self.owner_id=owner_id
        self.message=None
        self.stage="intro"
        self.result=None
        self.selected=None
        self.previous="intro"
        self._leaders=[]
        self._pick_lock=asyncio.Lock()
        self._draw()

    async def interaction_check(self, interaction):
        if (not interaction.guild or interaction.guild.id!=self.guild_id or
                interaction.user.id!=self.owner_id or interaction.user.bot):
            await fail(interaction,"Ce manoir appartient à un autre joueur.")
            return False
        return True

    def _stats(self):
        player=self.bot.store.profile(self.guild_id,self.owner_id)
        status=self.bot.store.trick_status(self.guild_id,self.owner_id)
        return player["candies"], status["streak"]

    def _view_file(self):
        candies,streak=self._stats()
        extra={"selected":self.selected, "result":self.result,
               "remaining":self.bot.store.trick_status(
                   self.guild_id,self.owner_id)["wait"]}
        if self.stage=="inventory":
            from .content import ITEMS
            names={"legendary_pumpkin":RARE_NAME}
            inv=self.bot.store.inventory(self.guild_id,self.owner_id)
            extra["inventory"]=[
                (x["item"],
                 (names.get(x["item"]) or ITEMS[x["item"]][0].split(" ",1)[-1])
                 if x["item"] in names or x["item"] in ITEMS else x["item"],
                 x["quantity"]) for x in inv
            ]
        elif self.stage=="leaderboard":
            extra["leaders"]=self._leaders
        return banner_file(self.stage,candies,streak,**extra)

    async def _resolved_leaders(self, guild):
        """Resolve Discord display names, including users not in member cache.

        Default bot intents do not populate the full member cache. A bounded
        REST lookup uses the real server nickname, falling back to account
        names or an anonymous rank — never showing raw snowflake IDs.
        """
        rows=self.bot.store.ranking(self.guild_id,"candies",5)

        async def resolve(index, row):
            uid=row["user_id"]
            member=guild.get_member(uid) if guild else None
            if member is None and guild and hasattr(guild,"fetch_member"):
                try:
                    member=await asyncio.wait_for(
                        guild.fetch_member(uid),timeout=2.5
                    )
                except (discord.HTTPException,discord.ClientException,
                        asyncio.TimeoutError):
                    pass
            if member is None and hasattr(self.bot,"fetch_user"):
                try:
                    member=await asyncio.wait_for(
                        self.bot.fetch_user(uid),timeout=2.5
                    )
                except (discord.HTTPException,discord.ClientException,
                        asyncio.TimeoutError):
                    pass
            name=getattr(member,"display_name",None) or \
                 getattr(member,"global_name",None) or \
                 getattr(member,"name",None)
            if name:
                # Avoid newlines, bidirectional/control surprises and mentions
                # in the PIL canvas while keeping international nicknames.
                name="".join(ch for ch in str(name)
                             if ch.isprintable() and ch not in "<>")
                name=name.strip()[:28]
            return (index, name or f"Chasseur #{index}", row["score"])

        return list(await asyncio.gather(
            *(resolve(i, row) for i, row in enumerate(rows,1))
        ))

    def _button(self, title, emoji, style, handler, disabled=False):
        b=discord.ui.Button(label=title, emoji=button_icon(emoji),
                            style=style, disabled=disabled)
        b.callback=handler
        return b

    def _draw(self):
        self.clear_items()
        self.add_item(_gallery())
        buttons=[]
        if self.stage=="intro":
            ready=self.bot.store.trick_status(
                self.guild_id,self.owner_id)["wait"]==0
            for i, emoji in enumerate(("key","pumpkin","ghost")):
                async def choose(interaction, index=i):
                    await self.choose(interaction,index)
                buttons.append(self._button(
                    f"Porte {i+1}",emoji,
                    (discord.ButtonStyle.primary if i==2
                     else discord.ButtonStyle.success if i==1
                     else discord.ButtonStyle.secondary),
                    choose,disabled=not ready,
                ))
            buttons.extend(self._navigation())
        elif self.stage=="opening":
            buttons.append(self._button(
                "La porte s'ouvre...", "clock",
                discord.ButtonStyle.secondary,self._nothing,disabled=True
            ))
        elif self.stage=="result":
            wait=self.bot.store.trick_status(
                self.guild_id,self.owner_id)["wait"]
            label=(f"Rejouer dans {(wait+59)//60} min"
                   if wait else "Rejouer")
            buttons.extend([
                self._button(label,"clock" if wait else "pumpkin",
                             discord.ButtonStyle.secondary if wait
                             else discord.ButtonStyle.success,self.replay),
                *self._navigation(),
            ])
        elif self.stage in ("inventory","leaderboard"):
            buttons.extend([
                self._button("Retour","key",discord.ButtonStyle.primary,
                             self.go_back),
                *self._navigation()
            ])
        else:
            buttons.append(self._button(
                "Partie expirée","lock",discord.ButtonStyle.secondary,
                self._nothing,disabled=True
            ))
        self.add_item(discord.ui.ActionRow(*buttons[:5]))

    async def _nothing(self, interaction):
        pass

    def _navigation(self):
        return [
            self._button("Inventaire","bag",discord.ButtonStyle.secondary,
                         self.show_inventory,
                         disabled=self.stage=="inventory"),
            self._button("Classement","trophy",discord.ButtonStyle.secondary,
                         self.show_leaderboard,
                         disabled=self.stage=="leaderboard"),
        ]

    async def _redraw(self,interaction):
        self._draw()
        kwargs=dict(
            view=self,attachments=[self._view_file()],
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if interaction.response.is_done():
            await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)

    async def show_inventory(self,interaction):
        async with self._pick_lock:
            if self.stage=="opening":
                return await fail(interaction,"Une porte est en train de s'ouvrir.")
            if self.stage not in ("inventory","leaderboard"):
                self.previous=self.stage
            self.stage="inventory"
            await self._redraw(interaction)

    async def show_leaderboard(self,interaction):
        async with self._pick_lock:
            if self.stage=="opening":
                return await fail(interaction,"Une porte est en train de s'ouvrir.")
            if self.stage not in ("inventory","leaderboard"):
                self.previous=self.stage
            # Discord needs an acknowledgment before the uncached-name lookups.
            await interaction.response.defer(thinking=False)
            self._leaders=await self._resolved_leaders(interaction.guild)
            self.stage="leaderboard"
            await self._redraw(interaction)

    async def go_back(self,interaction):
        async with self._pick_lock:
            self.stage=self.previous
            await self._redraw(interaction)

    async def replay(self,interaction):
        async with self._pick_lock:
            state=self.bot.store.trick_status(self.guild_id,self.owner_id)
            if state["wait"]:
                return await fail(interaction,wait_text(state["wait"]))
            self.stage="intro"
            self.result=None
            self.selected=None
            await self._redraw(interaction)

    async def choose(self,interaction,door):
        async with self._pick_lock:
            if self.stage!="intro":
                return await fail(interaction,"Cette porte est déjà fermée.")
            outcome=self.bot.store.play_trick(
                self.guild_id,self.owner_id,door
            )
            if outcome["status"]=="cooldown":
                return await fail(interaction,wait_text(outcome["wait"]))
            self.result=outcome
            self.selected=door
            self.stage="opening"
            await self._redraw(interaction)
            await asyncio.sleep(1.3)
            self.stage="result"
            self._draw()
            try:
                await interaction.edit_original_response(
                    view=self,attachments=[self._view_file()],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                LOG.exception("Trick-or-treat prize saved, but reveal edit failed")

    async def on_timeout(self):
        async with self._pick_lock:
            if self.stage=="opening":
                return
            if self.stage=="intro":
                self.stage="expired"
            self._draw()
            for row in self.children:
                if isinstance(row, discord.ui.ActionRow):
                    for button in row.children:
                        button.disabled=True
            if self.message is not None:
                try:
                    await self.message.edit(
                        view=self,attachments=[self._view_file()],
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.NotFound,discord.HTTPException):
                    LOG.debug("Cannot mark expired trick-or-treat view",exc_info=True)
            self.stop()
