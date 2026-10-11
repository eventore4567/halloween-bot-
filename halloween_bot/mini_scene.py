"""Live, individual 1280x700 gameboards for CRYPT CUP's seven mini-games.

Every interaction paints the actual current game state instead of attaching
the same static 310px banner for every stage. Native Discord buttons remain
interactive below ONE Components V2 MediaGallery; no duplicate grey embed.
"""
from __future__ import annotations

import math
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter

import discord

from .mini_art import COLORS
from .mini_engine import MODES, SYMBOLS, TTL_SECONDS
from .trick_or_treat import _write, _fit

W,H=1280,700
FILENAME="crypt-mini-jeu.jpg"
IVORY=(250,233,218)
MUTED=(193,183,204)
AMBER=(255,196,108)


def _box(d,coords,accent,*,fill=(17,14,30,242),radius=23):
    d.rounded_rectangle(coords,radius=radius,fill=fill,
                        outline=(*accent,195),width=3)


def _center(img, xy, text, size, color=IVORY):
    _write(img,xy,str(text),size,color,anchor="mm")


def _rune(d,x,y,kind,active=True):
    """Hand-drawn glyphs corresponding to the four native emoji choices."""
    ink=(250,214,145) if active else (113,104,128)
    if kind==0:  # crescent moon
        d.ellipse((x-29,y-32,x+29,y+32),fill=ink)
        d.ellipse((x-16,y-39,x+41,y+24),fill=(39,34,66))
    elif kind==1:  # bat
        d.polygon([(x,y-10),(x-20,y-20),(x-32,y-3),
                   (x-40,y+15),(x-17,y+10),(x,y+21),(x+17,y+10),
                   (x+40,y+15),(x+32,y-3),(x+20,y-20)],fill=ink)
        d.ellipse((x-4,y-14,x+4,y-2),fill=ink)
    elif kind==2:  # pumpkin
        d.ellipse((x-33,y-23,x+33,y+29),fill=ink)
        d.ellipse((x-19,y-23,x+19,y+29),outline=(131,69,45),width=3)
        d.rectangle((x-4,y-34,x+6,y-20),fill=(114,185,113))
    else:  # candle
        d.rounded_rectangle((x-13,y-13,x+13,y+29),radius=5,fill=ink)
        d.ellipse((x-9,y-37,x+9,y-10),fill=(255,159,90))
        d.line((x,y-13,x,y-8),fill=(50,34,44),width=3)


def _dice(d,x,y,value):
    d.rounded_rectangle((x-58,y-59,x+58,y+59),radius=23,
                        fill=(240,218,249),outline=(255,246,253),width=4)
    if value is None:
        return
    positions={
        1:[(0,0)],
        2:[(-28,-28),(28,28)],
        3:[(-28,-28),(0,0),(28,28)],
        4:[(-28,-28),(28,-28),(-28,28),(28,28)],
        5:[(-28,-28),(28,-28),(0,0),(-28,28),(28,28)],
        6:[(-28,-30),(28,-30),(-28,0),(28,0),(-28,30),(28,30)]
    }[value]
    for dx,dy in positions:
        d.ellipse((x+dx-9,y+dy-9,x+dx+9,y+dy+9),fill=(61,36,85))


def _text_lines(img,lines,accent):
    d=ImageDraw.Draw(img)
    y=252
    for idx,line in enumerate(lines):
        # True type pixel fitting, not font fallback. No Unicode emoji baked
        # in our static artwork: emoji are rendered natively on the buttons.
        if not line:
            y+=18
            continue
        words=str(line).split()
        part=""
        for word in words:
            candidate=(part+" "+word).strip()
            w=d.textbbox((0,0),candidate,
                         font=__import__("halloween_bot.trick_or_treat",
                                           fromlist=["_font"])._font(25))[2]
            if w>324 and part:
                _write(img,(869,y),part,25,IVORY)
                y+=34
                part=word
            else:
                part=candidate
        if part:
            _write(img,(869,y),part,25,AMBER if idx==0 else MUTED)
            y+=51
        if y>570:break


def _board(img,session,now):
    d=ImageDraw.Draw(img)
    mode=session.mode
    accent=COLORS[mode][2]
    state="result" if session.done else (
        "waiting" if now<session.ready_at else "active"
    )
    if mode=="memoire":
        for i in range(4):
            x=181+i*164
            _box(d,(x-62,300,x+62,446),accent,
                 fill=(39,34,66,245),radius=18)
            if state=="waiting" or (session.done and session.success):
                _rune(d,x,366,session.sequence[i])
            elif i<session.step:
                _rune(d,x,366,session.sequence[i])
            else:
                _center(img,(x,368), "?",54)
            _center(img,(x,468),f"{i+1:02}",21,MUTED)
        return (
            ["MÉMORISATION",f"Observe les runes pendant {math.ceil(session.ready_at-now)} s.",
             "Retrouve ensuite leur ordre."]
            if state=="waiting" else
            ["À TON TOUR",f"Rune {session.step+1}/4","Choisis le symbole suivant."]
            if not session.done else
            ["RITUEL TERMINÉ",session.last.replace("**","").replace("✨","").strip()]
        )
    if mode=="reflexe":
        if state=="waiting":
            d.ellipse((300,260,587,529),fill=(47,77,83),outline=(*accent,165),width=7)
            _center(img,(443,391),str(max(1,math.ceil(session.ready_at-now))),96,accent)
            lines=["LA BRUME SE LÈVE","Attends que le fantôme apparaisse.",
                   "Le bouton s'activera au signal."]
        else:
            d.ellipse((312,285,565,500),fill=(223,253,243))
            d.polygon([(318,420),(303,540),(350,505),(400,547),
                       (441,509),(500,543),(560,507),(561,425)],fill=(223,253,243))
            for xx in (402,483):
                d.ellipse((xx-12,380,xx+12,413),fill=(19,61,66))
            lines=(["MAINTENANT !","Attrape le fantôme.","Plus tu es rapide, plus tu gagnes."]
                   if not session.done else
                   ["FANTÔME CAPTURÉ",session.last.replace("**","").replace("⚡","").replace("👻","").strip()])
        return lines
    if mode=="labyrinthe":
        # Three masonry doors illustrate sequential progress.
        for i,x in enumerate((206,447,678)):
            locked=session.done or i<session.step
            d.polygon([(x-76,330),(x,242),(x+76,330)],
                      fill=(36,32,43),outline=(*accent,210),width=5)
            d.rounded_rectangle((x-65,322,x+65,509),radius=31,
                                fill=(27,25,34),outline=(*accent,255),width=4)
            if not locked:
                d.line((x,336,x,502),fill=(*accent,180),width=3)
                d.ellipse((x+32,418,x+43,429),fill=AMBER)
            else:
                _center(img,(x,425),"✓",55,accent)
            _center(img,(x,540),f"PORTE {i+1}",23,MUTED)
        if session.done:
            return ["PARCOURS TERMINÉ",session.last.replace("**","").strip()]
        return [f"PORTE {session.step+1}/3",
                session.puzzles[session.step][0],"Choisis la bonne porte."]
    if mode=="chaudron":
        # Pot, vapor and progressively added ingredients.
        d.ellipse((255,408,631,523),fill=(44,64,47),outline=(*accent,235),width=6)
        d.rounded_rectangle((286,437,602,559),radius=65,
                            fill=(47,50,53),outline=(158,178,155),width=7)
        d.ellipse((280,406,611,469),fill=(82,218,122),outline=(*accent,255),width=6)
        for i in range(3):
            x=335+i*104
            if i<session.step:
                d.ellipse((x-18,370,x+18,403),fill=(255,223,117))
            else:
                d.ellipse((x-13,370,x+13,396),outline=(134,151,126),width=4)
        for x,y in ((347,285),(442,259),(527,295)):
            d.ellipse((x-17,y-19,x+17,y+19),
                      outline=(*accent,220),width=4)
        if session.done:
            return ["POTION TERMINÉE",session.last.replace("**","").strip()]
        return [f"INGRÉDIENT {session.step+1}/3",
                session.puzzles[session.step][0],"Verse le bon ingrédient."]
    if mode=="coffres":
        chosen=getattr(session,"last_pick",None)
        for i,x in enumerate((167,348,528,706)):
            d.rounded_rectangle((x-66,364,x+66,494),radius=17,
                                fill=(115,62,38),outline=(*accent,255),width=7)
            d.arc((x-61,302,x+61,417),180,360,fill=(*accent,255),width=8)
            d.rounded_rectangle((x-13,414,x+13,443),radius=6,fill=AMBER)
            _center(img,(x,519),f"{i+1:02}",23,MUTED)
            if session.done:
                reward=session.chest_rewards[i]
                _center(img,(x,574),f"+{reward}",22,
                        accent if i==chosen else MUTED)
        return (["COFFRES RÉVÉLÉS","Le contenu des quatre coffres est visible.",
                 session.last.replace("**","").strip()] if session.done else
                ["LE CHOIX DU TRÉSOR","Ouvre un coffre parmi quatre.",
                 "Un seul choix, sans mise."])
    if mode=="des":
        _dice(d,328,389,session.demon_die)
        next_roll=getattr(session,"last_roll",None)
        _dice(d,613,389,next_roll)
        if next_roll is None:
            _center(img,(613,388),"?",55,(55,35,76))
        _center(img,(328,495),"DÉ INIT.",24,MUTED)
        _center(img,(613,495),"DÉ SUIVANT",24,MUTED)
        return (["RÉSULTAT DES DÉS",session.last.replace("**","").strip()]
                if session.done else
                ["DÉFI DU DÉMON","Prédit : supérieur, inférieur ou égal.",
                 "La valeur du prochain dé est secrète."])
    # fantomes : four graves, an actual parity clue.
    h=session.hidden_ghost
    for i,x in enumerate((165,346,528,708)):
        d.rounded_rectangle((x-60,329,x+61,517),radius=43,
                            fill=(52,80,95),outline=(*accent,215),width=5)
        d.line((x,366,x,412),fill=(182,223,228),width=5)
        d.line((x-23,389,x+24,389),fill=(182,223,228),width=5)
        if session.done and i==h:
            d.ellipse((x-34,293,x+34,354),fill=(219,251,248))
        _center(img,(x,543),str(i+1),26,accent)
    return (["CHASSE TERMINÉE",session.last.replace("**","").strip()]
            if session.done else
            ["UNE TRACE DANS LA BRUME",
             ("Le spectre se cache dans les tombes 1 ou 2."
              if h<2 else "Le spectre se cache dans les tombes 3 ou 4."),
             "Repère la bonne tombe !"])


def game_file(session, *, earned=0, now=None):
    """Render live board, then return a fresh File for every edit."""
    import time
    now=time.monotonic() if now is None else float(now)
    mode=session.mode
    first,second,accent=COLORS[mode]
    im=Image.new("RGBA",(W,H),(*first,255))
    d=ImageDraw.Draw(im)
    for y in range(H):
        f=y/(H-1)
        d.line((0,y,W,y),
               fill=tuple(round(first[i]*(1-f)+second[i]*f)
                          for i in range(3))+(255,))
    rnd=random.Random(178*len(mode))
    d=ImageDraw.Draw(im)
    for _ in range(54):
        x,y=rnd.randrange(50,1218),rnd.randrange(25,670)
        d.ellipse((x-1,y-1,x+1,y+1),fill=(*accent,140))
    _box(d,(20,18,1258,680),accent)
    _write(im,(57,40),"CRYPT CUP  /  MINI-JEU HALLOWEEN",21,MUTED)
    title=MODES[mode][0].upper()
    _write(im,(54,77),title,_fit(title,1100,size=56,min_size=37),
           accent,glow=2)
    _box(d,(47,173,836,621),accent,fill=(17,14,31,234))
    _box(d,(849,173,1231,621),accent,fill=(17,14,31,247))
    lines=_board(im,session,now)
    _write(im,(866,199),"TON AVENTURE",23,accent)
    d.line((867,238,1205,238),fill=(*accent,170),width=2)
    _text_lines(im,lines,accent)
    progress=(f"{session.step} / {4 if mode=='memoire' else 3}"
              if mode in ("memoire","labyrinthe","chaudron") and not session.done
              else "UNE PARTIE = UNE RÉCOMPENSE MAX")
    if session.done:
        _write(im,(869,546),f"+{earned} BONBONS",34,
               accent if earned else MUTED)
    else:
        _write(im,(868,549),progress,
               _fit(progress,325,size=22,min_size=17),MUTED)
    _write(im,(73,646),
           "PARTIE TERMINÉE" if session.done else
           f"TEMPS RESTANT : {max(0,math.ceil(session.deadline-now))} S",
           22,MUTED)
    if session.done:
        outcome="VICTOIRE" if session.success else "PARTIE PERDUE"
        _write(im,(1220,645),outcome,22,accent,anchor="ra")
    else:
        _write(im,(1220,645),"CHOISIS CI-DESSOUS",21,accent,anchor="ra")
    out=BytesIO()
    im.convert("RGB").save(out,"JPEG",quality=85,optimize=True)
    return discord.File(BytesIO(out.getvalue()),filename=FILENAME)
