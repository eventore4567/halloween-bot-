"""Full-height illustrated CRYPT CUP scene with live guild/player data.

The user's entire panel is ONE generated image. The text, glowing dates,
score, challenges, rank and progression are painted directly onto a continuous
Gothic/Halloween background, not stacked embeds or floating Discord fields.
Native buttons are rendered under the image in the same V2 Container.

Discord does not permit text or clickable buttons over a custom background.
A newly generated attachment gives the requested look while the action rows
remain native and functional; image data is an initial snapshot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from math import cos, pi, sin
from random import Random
from time import time

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1180, 1560
SCENE_FILE = "crypt-cup-scene.jpg"
SCENE_URI = f"attachment://{SCENE_FILE}"

NIGHT = (13, 9, 27)
PLUM = (35, 19, 51)
VIOLET = (164, 105, 251)
COPPER = (255, 163, 86)
CREAM = (254, 238, 219)
MIST = (205, 181, 225)
CYAN = (118, 200, 245)
GREEN = (132, 225, 183)
CORAL = (245, 127, 126)
SERIF = "DejaVuSerif-Bold.ttf"
SANS = "DejaVuSans.ttf"
SANS_BOLD = "DejaVuSans-Bold.ttf"


@lru_cache(maxsize=32)
def font(size, serif=False, bold=True):
    family=SERIF if serif else SANS_BOLD if bold else SANS
    alternatives=[
        "/usr/share/fonts/truetype/dejavu/"+family,
        family,
        "/usr/share/fonts/truetype/liberation2/"+(
            "LiberationSerif-Bold.ttf" if serif else
            "LiberationSans-Bold.ttf" if bold else
            "LiberationSans-Regular.ttf"
        ),
    ]
    for path in alternatives:
        try:
            return ImageFont.truetype(path,size)
        except (OSError,ValueError):
            pass
    return ImageFont.load_default(size=size)


def ellipse(draw,box,fill,outline=None,width=1):
    draw.ellipse(box,fill=fill,outline=outline,width=width)


def line(draw,coords,fill,width=3):
    draw.line(coords,fill=fill,width=width,joint="curve")


def centered(draw,x,y,caption,face,fill,outline=None):
    draw.text((x,y),caption,anchor="mm",font=face,fill=fill,
              stroke_width=1 if outline else 0,stroke_fill=outline)


def _flame(draw,x,y,s=1):
    flame=[(x,y-26*s),(x+10*s,y-8*s),(x+6*s,y+9*s),
           (x,y+16*s),(x-10*s,y+5*s),(x-8*s,y-9*s)]
    draw.polygon(flame,fill=(226,110,47))
    ellipse(draw,(x-5*s,y-2*s,x+5*s,y+11*s),(255,225,127))
    draw.rounded_rectangle((x-12*s,y+12*s,x+12*s,y+18*s),
                           radius=3*s,fill=(103,70,81))


def _spikes(draw,x,y,height,seed=1):
    rng=Random(seed)
    draw.rectangle((x,y-height,x+15,y+60),fill=(16,10,27))
    draw.polygon([(x-24,y-height),(x+7,y-height-64),
                  (x+39,y-height)],fill=(20,13,31))
    line(draw,[(x+7,y-height-64),(x+7,y-height-82)],(76,52,88),width=4)
    for _ in range(4):
        window_y=y-height+35+_*42
        ellipse(draw,(x+3,window_y,x+12,window_y+15),(181,94,47))


def _castle(draw):
    # Background silhouette is placed high up, while the middle is an empty
    # dark-purple field designed to hold legible player information.
    base=418
    dark=(13,10,26)
    draw.polygon([
        (746,base),(772,340),(810,311),(844,300),(867,244),(901,258),
        (931,181),(945,190),(958,276),(1012,231),(1048,291),
        (1099,255),(1145,330),(1180,350),(1180,465),(720,465)
    ],fill=dark)
    for x,height,seed in ((820,95,1),(930,178,2),(1065,132,3),(1140,65,4)):
        _spikes(draw,x,base,height,seed)
    for x,y in ((805,363),(857,332),(943,340),(982,301),
                (1090,348),(1138,390)):
        draw.rounded_rectangle((x-5,y-10,x+5,y+5),radius=4,
                               fill=(218,99,45))
    draw.arc((837,373,962,499),181,359,fill=(94,60,96),width=5)


def _moon(draw):
    # A rusty moon intentionally remains behind the spires, not under text.
    x,y,r=925,160,98
    for offset,color in ((46,(77,40,105)),(23,(124,60,113)),
                         (10,(176,99,105))):
        ellipse(draw,(x-r-offset,y-r-offset,x+r+offset,y+r+offset),
                fill=color)
    ellipse(draw,(x-r,y-r,x+r,y+r),fill=(239,161,114))
    # Woodcut-style craters.
    for cx,cy,radius in ((882,114,17),(969,136,21),(915,189,13),(971,204,9)):
        ellipse(draw,(cx-radius,cy-radius,cx+radius,cy+radius),
                fill=(211,126,100))
    ellipse(draw,(x+39,y-130,x+152,y-8),fill=(25,15,45))


def _bats(draw):
    for x,y,z in ((150,124,1.1),(386,89,.60),(702,177,.72),
                  (1083,83,.53),(1134,238,.68),(264,215,.45)):
        pts=[(-26,0),(-18,-8),(-8,-3),(0,4),(8,-3),(18,-8),
             (26,0),(13,-1),(7,9),(0,2),(-7,9),(-13,-1)]
        draw.polygon([(round(x+a*z),round(y+b*z)) for a,b in pts],
                     fill=(10,7,23))


def _arch_side(draw,x,side):
    # Gothic columns visually frame all content from top to bottom.
    draw.rectangle((x-16,0,x+16,HEIGHT),fill=(31,19,41))
    for y in (42,710,1215,1510):
        ellipse(draw,(x-26,y-21,x+26,y+21),
                fill=(59,33,66),outline=(139,78,109),width=3)
    for y in range(132,HEIGHT-90,160):
        draw.polygon([(x-14,y),(x+side*21,y+23),(x-14,y+49)],
                     fill=(88,46,89))
        line(draw,[(x,y+12),(x+side*8,y+25),(x,y+38)],
             (188,97,94),width=2)


def _portal(draw):
    cx,cy=145,280
    # Stylized mausoleum portal left of the title.
    draw.pieslice((53,161,237,348),180,360,fill=(62,31,86))
    draw.rectangle((53,250,237,393),fill=(58,30,82))
    draw.pieslice((69,178,221,331),180,360,
                  fill=(104,42,163),outline=(185,98,235),width=5)
    draw.rectangle((69,254,221,381),fill=(96,39,155))
    draw.pieslice((89,196,201,308),180,360,fill=(22,12,45))
    draw.rectangle((89,253,201,382),fill=(22,12,45))
    for dy in (212,246,280,314,348):
        line(draw,[(90,dy),(199,dy)],(58,31,86),width=2)
    ellipse(draw,(cx-13,264,cx+13,293),(179,106,231))
    line(draw,[(cx,291),(cx,343)],(196,127,252),width=7)
    for x in (72,216):
        _flame(draw,x,347,1)
    line(draw,[(49,393),(246,393)],(181,99,121),width=6)


@lru_cache(maxsize=1)
def background():
    picture=Image.new("RGB",(WIDTH,HEIGHT))
    d=ImageDraw.Draw(picture)
    # Rich nocturnal gradient with no patchwork cards and no background text.
    for y in range(HEIGHT):
        t=y/HEIGHT
        r=19 + int(7*t)
        g=10 + int(3*t)
        b=37 + int(14*t)
        d.line((0,y,WIDTH,y),fill=(r,g,b))
    # A quiet, violet aurora behind the castle.
    layer=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    glow=ImageDraw.Draw(layer)
    ellipse(glow,(560,6,1190,490),(107,49,131,95))
    ellipse(glow,(10,177,423,526),(86,35,114,90))
    ellipse(glow,(470,525,1085,1000),(51,26,83,65))
    layer=layer.filter(ImageFilter.GaussianBlur(80))
    picture=Image.alpha_composite(picture.convert("RGBA"),layer)
    d=ImageDraw.Draw(picture)
    _moon(d)
    _castle(d)
    _portal(d)
    # Uneven starfield / tiny distant runes.
    rng=Random(20261010)
    for _ in range(170):
        x=rng.randint(30,WIDTH-30)
        y=rng.randint(26,468)
        if (785<x<1070 and 45<y<255) or (470<x<750 and y>245):
            continue
        radius=rng.choices((1,2,3),weights=(7,4,1))[0]
        val=rng.randint(113,202)
        ellipse(d,(x-radius,y-radius,x+radius,y+radius),
                (val,int(val*.72),min(245,val+25)))
    _bats(d)

    # Fog rolling through the entire scene and behind the cards.
    fog=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    fd=ImageDraw.Draw(fog)
    for i in range(35):
        x=rng.randint(-300,WIDTH+150)
        y=rng.randint(335,HEIGHT-30)
        size=rng.randint(140,430)
        col=(92,65,126,rng.randint(8,27))
        ellipse(fd,(x,y-size//4,x+size,y+size//4),col)
    fog=fog.filter(ImageFilter.GaussianBlur(65))
    picture=Image.alpha_composite(picture,fog)

    ornament=ImageDraw.Draw(picture)
    # Pillars, stained glass studs and ornamented wrought-iron frame.
    _arch_side(ornament,35,1)
    _arch_side(ornament,WIDTH-35,-1)
    ornament.rounded_rectangle((57,44,1123,1519),radius=26,
                               outline=(133,77,137),width=4)
    ornament.rounded_rectangle((66,53,1114,1509),radius=24,
                               outline=(95,59,97),width=2)
    for x in (83,1098):
        for y in (79,465,900,1458):
            _flame(ornament,x,y,.65)
    for i in range(13):
        x=92+i*82
        line(ornament,[(x,1477),(x+18,1468),(x+35,1477)],
             (67,42,77),width=3)

    # Dim, translucent background behind all actual data; one continuous scene.
    veil=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    v=ImageDraw.Draw(veil)
    v.rounded_rectangle((91,457,1093,1435),radius=33,
                        fill=(13,9,28,159),outline=(155,86,153,130),width=3)
    for yy in (730,969,1292):
        v.line((130,yy,1050,yy),fill=(211,123,126,120),width=2)
    picture=Image.alpha_composite(picture,veil)
    return picture.convert("RGBA")


def _text(picture,xy,value,size,*,color=CREAM,serif=False,bold=True,
          glow=False,anchor=None,outline=0):
    """Draw crisp lettering with a subtle halo without making it blurry."""
    face=font(size,serif=serif,bold=bold)
    if glow:
        shadow=Image.new("RGBA",picture.size,(0,0,0,0))
        sd=ImageDraw.Draw(shadow)
        sd.text(xy,value,font=face,fill=(*color,190),
                anchor=anchor,stroke_width=3,
                stroke_fill=(color[0],color[1],color[2],140))
        aura=shadow.filter(ImageFilter.GaussianBlur(12))
        picture.alpha_composite(aura)
    d=ImageDraw.Draw(picture)
    d.text(xy,value,font=face,fill=color,anchor=anchor,
           stroke_width=outline,stroke_fill=NIGHT if outline else None)


def _fit(value, width, max_size=43, min_size=24,serif=False):
    for sz in range(max_size,min_size-1,-1):
        b=ImageDraw.Draw(Image.new("RGB",(1,1)))
        box=b.textbbox((0,0),value,font=font(sz,serif=serif))
        if box[2]-box[0] <= width:
            return sz
    return min_size


def _remaining(seconds):
    seconds=max(0,int(seconds))
    if seconds<60:
        return f"{seconds} secondes"
    if seconds<3600:
        return f"{seconds//60} min {seconds%60:02} s"
    if seconds<86400:
        return f"{seconds//3600} h {seconds%3600//60:02} min"
    return f"{seconds//86400} jours {seconds%86400//3600} h"


def _ui_state(bot,guild,user,now):
    season=bot.competition.season(guild.id)
    current=bot.round_store.current(guild.id)
    config=bot.round_store.config(guild.id)
    entry=bot.competition.position(guild.id,user.id)
    if not season:
        portal="PORTAIL FERMÉ"
        status="La compétition n'a pas encore commencé."
        next_note="OUVERTURE PAR UN ORGANISATEUR AVEC /SETUP"
        color=CORAL
    elif season["status"]!="active":
        portal="SAISON TERMINÉE"
        status="Le classement est consultable."
        next_note="EN ATTENTE DE VALIDATION DES RÉSULTATS"
        color=CORAL
    elif current and current["status"]=="signup":
        portal="INSCRIPTIONS OUVERTES"
        status=f"{bot.round_store.count(current['id'])} participants dans l'arène"
        next_note=f"FERMETURE DANS {_remaining(current['signup_ends_at']-now)}"
        color=GREEN
    elif current and current["status"]=="active":
        portal="LA CRYPTE EST OUVERTE"
        status=f"{bot.round_store.count(current['id'])} chasseurs inscrits"
        next_note=f"FIN DE MANCHE DANS {_remaining(current['ends_at']-now)}"
        color=CORAL
    else:
        portal="LE PORTAIL SE PRÉPARE"
        status="La prochaine manche approche."
        delta=config.get("next_at",0)
        next_note=(f"OUVERTURE DANS {_remaining(delta-now)}"
                   if delta and config.get("enabled")
                   else "SURVEILLE LES ANNONCES DU SERVEUR")
        color=MIST

    from .competition_store import division
    if entry:
        grade,cap,_=division(entry["score"])
        grade=grade.split(" ",1)[-1].upper()
        place=f"#{entry['place']}"
        score=f"{entry['score']:,}"
        level_fraction=entry["score"]/cap if cap else 0
        target=f"PALIER SUIVANT : {max(0,cap-entry['score']):,} POINTS"
    else:
        place="—"
        score="0"
        grade="BRONZE"
        level_fraction=0
        target="TA PREMIÈRE VICTOIRE ATTEND TON NOM"

    prize=(season or {}).get("prize_label") or config.get("prize_label") or ""
    return dict(
        portal=portal,status=status,next_note=next_note,
        portal_color=color,place=place,score=score,grade=grade,
        fraction=min(1,max(0,level_fraction)),target=target,prize=prize,
        time_label=datetime.fromtimestamp(now,timezone.utc).strftime("%H:%M UTC"),
    )


def _glow_rule(image,y, color=COPPER):
    line_draw=ImageDraw.Draw(image)
    line_draw.line((146,y,1034,y),fill=(*color,126),width=2)
    ellipse(line_draw,(133,y-6,145,y+6),fill=(*color,200))
    ellipse(line_draw,(1035,y-6,1047,y+6),fill=(*color,200))


def _scene(bot,guild,user,now):
    data=_ui_state(bot,guild,user,now)
    image=background().copy()
    d=ImageDraw.Draw(image)

    # The typography is part of the backdrop, not a Discord TextDisplay.
    _text(image,(585,101),"H A L L O W E E N    2 0 2 6",
          25,color=MIST,anchor="mm")
    _text(image,(590,250),"CRYPT CUP",100,color=COPPER,
          serif=True,glow=True,anchor="mm",outline=2)
    _text(image,(592,342),"LE SANCTUAIRE DES OMBRES",32,
          color=CREAM,anchor="mm",glow=True)
    _text(image,(590,414),"UN PORTAIL  •  TROIS ÉPREUVES  •  UN TITRE",
          21,color=MIST,anchor="mm",bold=False)
    _glow_rule(image,458)

    _text(image,(140,508),"LE PORTAIL DES BRUMES",42,
          color=CREAM,serif=True,glow=True)
    _text(image,(140,581),data["portal"],
          _fit(data["portal"],760,49,32),
          color=data["portal_color"],glow=True)
    _text(image,(140,632),data["status"],28,color=CREAM,bold=False)
    _text(image,(140,685),data["next_note"],
          _fit(data["next_note"],875,27,17),
          color=MIST)
    _glow_rule(image,728)

    _text(image,(140,766),"TON BLASON DE CHASSEUR",42,
          color=CREAM,serif=True,glow=True)
    labels=[("RANG",data["place"]),("DIVISION",data["grade"]),
            ("POINTS",data["score"])]
    for i,(label,value) in enumerate(labels):
        left=144+321*i
        _text(image,(left,835),label,22,color=MIST)
        _text(image,(left,871),str(value),42,color=COPPER,glow=True)
    d.rounded_rectangle((145,921,1029,938),radius=8,
                        fill=(69,50,78),outline=(99,61,103),width=2)
    fraction=data["fraction"]
    if fraction:
        d.rounded_rectangle((145,921,145+int(884*fraction),938),
                            radius=8,fill=(211,133,113))
    _text(image,(145,952),data["target"],
          _fit(data["target"],865,21,16),
          color=MIST)
    _glow_rule(image,976)

    _text(image,(142,1013),"LES TROIS ÉPREUVES",43,
          color=CREAM,serif=True,glow=True)
    tiles=[
        ("ALCHIMIE","LOGIQUE ET CALCUL","100",VIOLET),
        ("MOTS MAUDITS","CULTURE ET RÉFLEXION","130",COPPER),
        ("CODE DE LA CRYPTE","ÉNIGMES ET DÉDUCTION","160",CYAN)
    ]
    for idx,(name,desc,points,tint) in enumerate(tiles):
        x1=139+idx*310
        x2=x1+288
        y1=1086
        d.rounded_rectangle((x1,y1,x2,1266),
                            radius=17,fill=(36,25,47,219),
                            outline=(*tint,230),width=3)
        d.line((x1+22,y1+25,x2-22,y1+25),fill=tint,width=2)
        _text(image,((x1+x2)//2,1140),name,
              _fit(name,267,23,18),
              color=tint,anchor="mm",glow=True)
        _text(image,((x1+x2)//2,1185),desc,
              _fit(desc,275,17,13),
              color=CREAM,anchor="mm",bold=False)
        _text(image,((x1+x2)//2,1228),points+" PTS",
              30,color=CREAM,anchor="mm")
    _glow_rule(image,1290)

    _text(image,(590,1325),"LA RÉCOMPENSE DU SANCTUAIRE",
          33,color=COPPER,serif=True,anchor="mm",glow=True)
    prize=data["prize"]
    if prize:
        headline="PRIX ANNONCÉ : "+prize
        notice="VÉRIFICATION ET RÈGLEMENT PAR LES ORGANISATEURS"
    else:
        headline="LA GLOIRE ET LE CLASSEMENT"
        notice="AUCUN PRIX RÉEL N'EST ANNONCÉ POUR LE MOMENT"
    _text(image,(590,1372),headline,
          _fit(headline,880,37,19),color=CREAM,anchor="mm",glow=True)
    _text(image,(590,1421),notice,_fit(notice,860,18,13),
          color=MIST,anchor="mm",bold=False)
    _text(image,(590,1486),
          "ÉTAT À "+data["time_label"]+
          "  •  POUR ACTUALISER, RELANCE /competition",
          14,color=(175,143,186),anchor="mm",bold=False)
    return image.convert("RGB")


def build_scene(bot,guild,user,now=None) -> bytes:
    """Create the current guild/member-specific artwork as a JPEG."""
    now=int(time() if now is None else now)
    image=_scene(bot,guild,user,now)
    result=BytesIO()
    image.save(result,format="JPEG",quality=83,optimize=True,subsampling=1)
    return result.getvalue()


def competition_scene_file(bot,guild,user,now=None)->discord.File:
    return discord.File(BytesIO(build_scene(bot,guild,user,now)),
                        filename=SCENE_FILE)
