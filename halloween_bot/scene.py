"""CRYPT CUP: legible cinematic artwork sized for Discord's actual message width.

Discord shrinks tall MediaGallery images to fit into a narrow portrait preview.
The former 1180x1560 scene made almost every status and reward unreadable.
This 1280x840 LANDSCAPE scene prioritizes hierarchy and real legibility:
hero title > two large live data regions > three challenges. Fine details and
long paragraphs are handled by the interactive native buttons, not tiny art.
Every number is read from the persistent competition store at invocation time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from random import Random
from time import time

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import pathlib as _pathlib
_FONTS = _pathlib.Path(__file__).resolve().parent / "fonts"

WIDTH, HEIGHT = 1280, 840
SCENE_FILE = "crypt-cup-scene.jpg"
SCENE_URI = f"attachment://{SCENE_FILE}"

INK = (17, 11, 31)
BLACK = (10, 7, 20)
PURPLE = (53, 27, 71)
MAGENTA = (186, 116, 250)
ORANGE = (247, 169, 96)
IVORY = (255, 242, 223)
SOFT = (226, 202, 235)
TEAL = (130, 211, 223)
MINT = (140, 229, 182)
ROSE = (255, 142, 155)
SERIF = "DejaVuSerif-Bold.ttf"
SANS = "DejaVuSans.ttf"
SANS_BOLD = "DejaVuSans-Bold.ttf"


@lru_cache(maxsize=64)
def _font(size, *, serif=False, bold=True):
    family = SERIF if serif else SANS_BOLD if bold else SANS
    for name in (
        # Police embarquée d'abord : sur l'hébergement, DejaVu n'est pas installée
        # et Pillow retombait sur une police sans accents (« FERM☒ »).
        str(_FONTS / family),
        "/usr/share/fonts/truetype/dejavu/"+family,
        family,
        "/usr/share/fonts/truetype/liberation2/"+(
            "LiberationSerif-Bold.ttf" if serif else
            "LiberationSans-Bold.ttf" if bold else
            "LiberationSans-Regular.ttf"),
    ):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, ValueError):
            pass
    return ImageFont.load_default(size=size)


def _fit(text, max_width, *, size=50, min_size=30, serif=False):
    helper=ImageDraw.Draw(Image.new("RGB",(1,1)))
    for n in range(size,min_size-1,-1):
        box=helper.textbbox((0,0),str(text),font=_font(n,serif=serif))
        if box[2]-box[0] <= max_width:
            return n
    return min_size


def _lettering(image, xy, text, size, *, color=IVORY, glow=0, serif=False,
               bold=True, anchor=None):
    f=_font(size,serif=serif,bold=bold)
    if glow:
        effect=Image.new("RGBA",image.size,(0,0,0,0))
        shadow=ImageDraw.Draw(effect)
        shadow.text(xy,str(text),font=f,fill=(*color,155),
                    anchor=anchor,stroke_width=2,stroke_fill=(*color,75))
        image.alpha_composite(effect.filter(ImageFilter.GaussianBlur(glow)))
    d=ImageDraw.Draw(image)
    d.text(xy,str(text),font=f,anchor=anchor,fill=(*color,255),
           stroke_width=1,stroke_fill=(13,8,25,190))


def _frame(draw,coords,color,thick=2):
    x1,y1,x2,y2=coords
    draw.rounded_rectangle((x1,y1,x2,y2),radius=21,
                           outline=(*color,175),width=thick)
    for x in (x1+19,x2-19):
        for y in (y1+18,y2-18):
            draw.ellipse((x-3,y-3,x+3,y+3),fill=(*color,200))


def _rule(draw,x1,y,x2,color=ORANGE):
    draw.line((x1,y,x2,y),fill=(*color,108),width=2)
    for xx in (x1,x2):
        draw.ellipse((xx-5,y-5,xx+5,y+5),fill=(*color,200))


def _glimmer(draw,x,y,scale=1,color=SOFT):
    radius=round(7*scale)
    draw.line((x-radius,y,x+radius,y),fill=(*color,185),width=2)
    draw.line((x,y-radius,x,y+radius),fill=(*color,185),width=2)


def _castle(draw):
    dark=(15,9,26,255)
    # Tall silhouettes on right; left header stays clear of objects.
    draw.polygon([(850,287),(884,231),(918,246),(945,194),(979,217),
                  (1014,136),(1044,166),(1080,205),(1124,180),
                  (1152,240),(1208,206),(1280,266),(1280,322),
                  (846,322)],fill=dark)
    for x,y,h in ((879,155,143),(1002,89,219),(1127,134,171)):
        draw.rectangle((x,y+45,x+39,303),fill=dark)
        draw.polygon([(x-17,y+45),(x+19,y-24),(x+57,y+45)],fill=dark)
        draw.line((x+19,y-22,x+19,y-40),fill=(74,45,86,255),width=3)
        for wy in range(y+100,283,49):
            draw.rounded_rectangle((x+15,wy,x+24,wy+18),
                                   radius=4,fill=(219,123,77,255))
    draw.arc((920,250,1070,350),180,350,fill=(124,65,117,255),width=5)


def _arch(draw):
    # Hand-drawn gothic arch integrates the left border with the whole scene.
    ink=(18,10,35,240)
    draw.pieslice((45,100,334,384),180,360,fill=(65,33,84,135),
                  outline=(161,90,156,255),width=5)
    draw.rectangle((45,242,333,396),fill=(50,25,69,150))
    draw.pieslice((76,132,300,360),180,360,fill=ink,
                  outline=(133,83,169,255),width=6)
    draw.rectangle((76,250,300,387),fill=ink)
    draw.line((183,215,183,380),fill=(100,58,132,255),width=5)
    draw.ellipse((171,248,196,272),fill=(175,105,220,255))
    draw.rounded_rectangle((180,268,188,308),radius=4,
                           fill=(175,105,220,255))


def _bat(draw,x,y,factor):
    p=[(-24,0),(-15,-8),(-8,-2),(0,5),(8,-2),
       (15,-8),(24,0),(11,-2),(5,8),(0,3),
       (-5,8),(-11,-2)]
    draw.polygon([(x+round(dx*factor),y+round(dy*factor))
                  for dx,dy in p],fill=(14,9,26,255))


def _ghost_trees(draw):
    for x in (6,1230):
        draw.line((x,65,x,850),fill=(27,15,35,235),width=24)
        for yy in (110,220,380,550,700):
            direction=1 if x==6 else -1
            draw.line((x,yy,x+direction*60,yy-55),
                      fill=(27,15,35,235),width=10)
            draw.line((x+direction*54,yy-50,
                       x+direction*78,yy-115),
                      fill=(27,15,35,235),width=5)


@lru_cache(maxsize=1)
def _base():
    img=Image.new("RGBA",(WIDTH,HEIGHT))
    draw=ImageDraw.Draw(img)
    for y in range(HEIGHT):
        f=y/HEIGHT
        draw.line((0,y,WIDTH,y),
                  fill=(int(26+10*f),int(13+6*f),int(49+13*f),255))
    clouds=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    cd=ImageDraw.Draw(clouds)
    cd.ellipse((580,-250,1330,430),fill=(142,56,159,90))
    cd.ellipse((-120,90,620,600),fill=(93,38,125,62))
    cd.ellipse((250,420,1100,950),fill=(89,54,116,60))
    img.alpha_composite(clouds.filter(ImageFilter.GaussianBlur(95)))
    d=ImageDraw.Draw(img)

    # Carved copper moon.
    d.ellipse((970,-75,1280,234),fill=(137,60,120,170))
    d.ellipse((1024,-20,1242,196),fill=(248,176,113,255))
    for x,y,r in ((1090,53,24),(1184,88,16),(1116,126,12)):
        d.ellipse((x-r,y-r,x+r,y+r),fill=(207,125,99,255))
    d.ellipse((1148,-67,1296,112),fill=(37,19,58,255))
    _castle(d)
    _arch(d)
    _ghost_trees(d)
    rng=Random(20261031)
    for _ in range(160):
        x=rng.randint(40,WIDTH-40)
        y=rng.randint(22,335)
        if (x<360 and y>140) or (x>970 and y<210):
            continue
        radius=rng.choice((1,1,1,2,2,3))
        opacity=rng.randint(105,215)
        d.ellipse((x-radius,y-radius,x+radius,y+radius),
                  fill=(202,163,236,opacity))
    for x,y,z in ((403,110,.8),(697,69,.6),(856,122,.7),
                  (1170,256,.4),(552,210,.5)):
        _bat(d,x,y,z)

    # Unified dark glass layer (not stacked solid colored cards).
    shade=Image.new("RGBA",img.size,(0,0,0,0))
    sd=ImageDraw.Draw(shade)
    sd.rounded_rectangle((40,34,1240,810),radius=28,
                         outline=(185,104,167,180),width=4)
    sd.rounded_rectangle((52,46,1228,799),radius=24,
                         outline=(134,77,130,130),width=2)
    # The title uses an open scene. The information lives on translucent
    # carved glass panels in the same environment, not an extra embed.
    sd.rounded_rectangle((78,331,1205,606),radius=19,
                         fill=(10,7,24,185),
                         outline=(188,101,160,180),width=3)
    sd.line((638,366,638,579),fill=(188,110,169,145),width=3)
    sd.rounded_rectangle((78,641,1205,785),radius=17,
                         fill=(12,8,29,196),
                         outline=(180,106,168,160),width=3)
    img.alpha_composite(shade)
    d=ImageDraw.Draw(img)
    _rule(d,110,317,1176)
    _rule(d,110,622,1176)
    for x,y in ((87,43),(1192,43),(87,793),(1192,793)):
        _glimmer(d,x,y,1.0,ORANGE)
    for x,y in ((95,346),(1188,346),(95,772),(1188,772)):
        _glimmer(d,x,y,.70,SOFT)

    # Sprinkles of fog behind the data areas rather than on top of glyphs.
    return img


def _state(bot,guild,user,now):
    season=bot.competition.season(guild.id)
    active=bot.round_store.current(guild.id)
    cfg=bot.round_store.config(guild.id)
    entry=bot.competition.position(guild.id,user.id)
    if not season:
        status="PORTAIL FERMÉ"
        countdown="Ouverture par un organisateur"
        color=ROSE
    elif season["status"]!="active":
        status="SAISON TERMINÉE"
        countdown="Résultats en vérification"
        color=SOFT
    elif active and active["status"]=="signup":
        status="INSCRIPTIONS OUVERTES"
        delta=max(0,active["signup_ends_at"]-now)
        countdown=f"Fermeture dans {delta//60} min"
        color=MINT
    elif active and active["status"]=="active":
        status="ÉPREUVE EN COURS"
        delta=max(0,active["ends_at"]-now)
        countdown=f"Fin dans {delta//60} min"
        color=ROSE
    else:
        status="PROCHAINE MANCHE"
        delta=cfg.get("next_at") or 0
        countdown=(f"Dans {max(0,delta-now)//60} min"
                   if cfg.get("enabled") and delta else
                   "Annonce à venir")
        color=SOFT
    from .competition_store import division
    if entry:
        grade,_,_=division(entry["score"])
        rank=str(entry["place"])
        points=str(entry["score"])
        tier=grade.replace("🥉 ","").replace("🥈 ","").replace("🥇 ","")
    else:
        rank="—"
        points="0"
        tier="BRONZE"
    return {
        "status":status, "countdown":countdown, "color":color,
        "rank":rank, "points":points, "tier":tier.upper(),
        "stamp":datetime.fromtimestamp(now,timezone.utc).strftime("%H:%M UTC"),
    }


def _decor_icon(canvas,name,x,y,width=60):
    """Application-owned original emojis are composited into the scene."""
    from .emoji_art import render_emoji
    try:
        source=Image.open(BytesIO(render_emoji(name))).convert("RGBA")
        icon=source.resize((width,width),Image.Resampling.LANCZOS)
        canvas.alpha_composite(icon,(x,y))
    except (OSError,ValueError):
        pass


def _scene(bot,guild,user,now):
    values=_state(bot,guild,user,now)
    im=_base().copy()
    # Hero kept left of the castle and moon.
    _lettering(im,(400,117),"HALLOWEEN 2026",25,
               color=SOFT,anchor="mm")
    _lettering(im,(400,205),"CRYPT CUP",103,
               color=ORANGE,glow=9,serif=True,anchor="mm")
    _lettering(im,(401,279),"LE SANCTUAIRE DES OMBRES",34,
               color=IVORY,glow=4,anchor="mm")

    # Two large, balanced areas rather than many tiny unreadable lines.
    _decor_icon(im,"key",101,361,64)
    _lettering(im,(173,372),"LE PORTAIL",39,color=SOFT,serif=True)
    state=values["status"]
    _lettering(im,(108,448),state,_fit(state,505,size=57,min_size=42),
               color=values["color"],glow=6)
    note=values["countdown"]
    _lettering(im,(110,525),note,_fit(note,498,size=31,min_size=25),
               color=IVORY,bold=False)

    _decor_icon(im,"crown",665,361,65)
    _lettering(im,(738,372),"TON PARCOURS",39,color=SOFT,serif=True)
    _lettering(im,(676,449),"RANG "+values["rank"],
               _fit("RANG "+values["rank"],480,size=56,min_size=43),
               color=ORANGE,glow=5)
    _lettering(im,(680,521),
               values["tier"]+"  ·  "+values["points"]+" PTS",
               _fit(values["tier"]+"  ·  "+values["points"]+" PTS",470,
                    size=32,min_size=25),
               color=IVORY,bold=False)

    _decor_icon(im,"book",106,655,58)
    _lettering(im,(174,667),"LES TROIS ÉPREUVES",39,
               color=IVORY,serif=True,glow=4)
    # Clear 3-column points with no microscopic descriptions.
    drills=[
        ("ALCHIMIE","100 PTS",MAGENTA,117),
        ("MOTS MAUDITS","130 PTS",ORANGE,492),
        ("CODE DE LA CRYPTE","160 PTS",TEAL,837),
    ]
    for name,score,shade,x in drills:
        _lettering(im,(x,719),name,
                   _fit(name,317,size=32,min_size=26),
                   color=shade,glow=4)
        _lettering(im,(x,766),score,33,color=IVORY)

    # Snapshot reminder is deliberately outside the illustration and native
    # in the command; no 13px line hidden at the very bottom of the picture.
    return im.convert("RGB")


def build_scene(bot,guild,user,now=None)->bytes:
    now=int(time() if now is None else now)
    result=BytesIO()
    _scene(bot,guild,user,now).save(
        result,format="JPEG",quality=86,optimize=True,subsampling=1)
    return result.getvalue()


def competition_scene_file(bot,guild,user,now=None)->discord.File:
    return discord.File(BytesIO(build_scene(bot,guild,user,now)),
                        filename=SCENE_FILE)
