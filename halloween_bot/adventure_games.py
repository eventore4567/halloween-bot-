"""Five genuinely different Halloween experiences, not repeated trivia screens.

One public message per game; illustrated Components V2 with real buttons.
Only the initiating player controls solo games; duel has two participants and
boss is cooperative. Rewards remain *virtual candy*, never competition euros.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFilter

from .common import button_icon, fail, wait_text
from .content import HUNTS
from .trick_or_treat import _font, _fit, _write

LOG = logging.getLogger(__name__)
FILE = "crypt-aventure.jpg"
URI = f"attachment://{FILE}"
W,H = 1280,700
TEXT=(253,235,220)
GOLD=(255,193,111)
FADE=(211,189,216)
PALE=(239,219,245)
PALETTE={
    "ghosthunt":((6,35,47),(18,72,81),(106,227,205)),
    "pumpkin":((43,18,22),(130,52,27),(255,160,69)),
    "expedition":((21,17,35),(56,39,64),(178,147,232)),
    "duel":((39,11,30),(115,25,49),(255,126,150)),
    "boss":((39,11,21),(105,34,21),(255,167,83)),
}


def _base(kind):
    a,b,glow=PALETTE[kind]
    im=Image.new("RGBA",(W,H),(0,0,0,255))
    d=ImageDraw.Draw(im)
    for y in range(H):
        factor=y/(H-1)
        d.line((0,y,W,y),fill=tuple(round(a[i]*(1-factor)+b[i]*factor) for i in range(3))+(255,))
    rnd=random.Random({"ghosthunt":12,"pumpkin":22,"expedition":32,"duel":42,"boss":52}[kind])
    sparks=Image.new("RGBA",(W,H))
    s=ImageDraw.Draw(sparks)
    for _ in range(63):
        x,y=rnd.randrange(40,1240),rnd.randrange(60,560)
        r=rnd.choice((1,1,2,3))
        s.ellipse((x-r,y-r,x+r,y+r),fill=(*glow,rnd.randrange(70,160)))
    im.alpha_composite(sparks)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((22,19,1257,677),radius=29,
                        outline=(*glow,200),width=3)
    d.rounded_rectangle((52,45,1225,160),radius=19,
                        fill=(8,8,19,190),outline=(*glow,155),width=2)
    _write(im,(77,57),"CRYPT CUP  /  HALLOWEEN",22,FADE)
    return im


def _art(im,kind,stage,info):
    d=ImageDraw.Draw(im)
    color=PALETTE[kind][2]
    if kind=="ghosthunt":
        # Misted graveyard, three real hiding places, and a roaming spectre.
        for j,x in enumerate((180,401,638)):
            d.rounded_rectangle((x-57,347,x+90,522),radius=46,
                                fill=(35,56,67),outline=(108,192,183),width=4)
            d.line((x+16,375,x+16,412),fill=(130,204,204),width=6)
            d.line((x-4,394,x+36,394),fill=(130,204,204),width=6)
            _write(im,(x+17,533),("01","02","03")[j],24,FADE,anchor="mm")
        d.ellipse((284,225,465,355),fill=(183,246,232,55))
        if stage=="result" and info.get("caught"):
            x,y=444,280
            d.ellipse((x-75,y-54,x+75,y+92),fill=(228,247,253))
            d.polygon([(x-74,y+40),(x-81,y+113),(x-35,y+84),
                       (x+2,y+122),(x+48,y+88),(x+80,y+113),(x+74,y+48)],
                      fill=(228,247,253))
            for xx in (x-24,x+24):
                d.ellipse((xx-10,y+12,xx+10,y+37),fill=(32,48,70))
        else:
            for x,y in ((257,250),(542,284),(687,240)):
                d.line((x-10,y,x+10,y),fill=(172,249,232),width=3)
                d.line((x,y-10,x,y+10),fill=(172,249,232),width=3)
        _write(im,(420,592),"LE CIMETIÈRE BRUMEUX",30,color,anchor="mm")
    elif kind=="pumpkin":
        # Actual orchard pumpkins; cracks are drawn progressively.
        for x in (136,363,584):
            d.line((x+75,200,x+75,327),fill=(93,72,39),width=18)
            d.ellipse((x+9,222,x+141,342),fill=(97,63,36))
        count=info.get("cracks",0)
        selected=info.get("choice")
        for j,x in enumerate((129,352,575)):
            active=selected is None or selected==j
            shade=((247,139,66),(180,102,218),(229,164,73))[j]
            d.ellipse((x-40,339,x+172,518),
                      fill=(*shade,255) if active else (84,59,66))
            d.ellipse((x-1,342,x+132,518),
                      fill=(255,169,82) if active else (104,67,73))
            d.line((x+62,339,x+57,307),fill=(85,148,68),width=14)
            d.polygon([(x+9,424),(x+34,452),(x-4,454)],fill=(40,20,30))
            d.polygon([(x+107,424),(x+93,452),(x+130,454)],fill=(40,20,30))
            d.arc((x+8,445,x+112,495),0,175,fill=(46,21,32),width=10)
            if j==selected:
                for crack in range(count):
                    xx=x+54+crack*12
                    d.line((xx,340,xx-17,385,xx+8,419),fill=(56,27,40),width=5)
        _write(im,(424,593),"LE VERGER DES CITROUILLES",28,color,anchor="mm")
    elif kind=="expedition":
        # Perspective stone corridor and map-style three branches.
        d.polygon([(80,226),(745,226),(654,544),(175,544)],
                  fill=(38,29,49),outline=(*color,220),width=4)
        for y in (305,382,459,531):
            d.line((105,y,723,y),fill=(99,82,120),width=2)
        for i,x in enumerate((203,401,608)):
            d.polygon([(x-82,310),(x,215),(x+80,310)],
                      fill=(19,14,36),outline=(*color,170),width=4)
            d.rounded_rectangle((x-72,301,x+73,502),radius=37,
                                fill=(29,22,45),outline=(*color,220),width=4)
            d.ellipse((x+39,390,x+48,400),fill=GOLD)
            _write(im,(x,522),("CRYPTE","GRENIER","CAVE")[i],22,PALE,anchor="mm")
        d.polygon([(422,562),(382,594),(462,594)],fill=GOLD)
    elif kind=="duel":
        # Two distinct armed silhouettes, central arena and dual HP bars.
        d.ellipse((92,470,756,577),fill=(14,10,28))
        for x,color2,flip in ((272,(225,129,164),-1),(595,(151,173,245),1)):
            d.ellipse((x-54,274,x+54,381),fill=(*color2,255))
            d.polygon([(x-79,382),(x+72,382),(x+117,512),(x-120,512)],
                      fill=(*color2,235))
            d.line((x+flip*46,398,x+flip*144,278),fill=(235,233,240),width=9)
            d.line((x+flip*104,330,x+flip*167,356),fill=GOLD,width=9)
        d.ellipse((390,286,477,373),outline=(*color,250),width=6)
        _write(im,(434,321),"VS",37,GOLD,anchor="mm")
        names=info.get("names",("JOUEUR 1","JOUEUR 2"))
        hp=info.get("hp",(100,100))
        for x,name,value,col in ((90,names[0],hp[0],(244,121,158)),
                                 (455,names[1],hp[1],(166,163,255))):
            _write(im,(x,203),name[:18].upper(),23,TEXT)
            d.rounded_rectangle((x,247,x+288,269),radius=8,fill=(33,24,43))
            if value>0:
                d.rounded_rectangle((x,247,x+round(288*value/100),269),
                                    radius=7,fill=(*col,255))
        _write(im,(420,595),"L'ARÈNE DU DUEL",28,color,anchor="mm")
    elif kind=="boss":
        # Giant three-phase pumpkin boss over lava with a real HP display.
        d.polygon([(75,535),(235,486),(396,523),(551,478),(751,536),
                   (751,574),(77,573)],fill=(177,71,33))
        d.ellipse((225,206,602,519),fill=(191,70,28),outline=(255,165,78),width=8)
        d.ellipse((279,208,545,511),fill=(246,123,37))
        d.ellipse((349,210,472,513),fill=(255,170,60))
        d.polygon([(393,211),(377,176),(432,166),(438,209)],fill=(90,134,55))
        d.polygon([(318,332),(358,386),(293,389)],fill=(34,23,37))
        d.polygon([(503,330),(467,388),(527,388)],fill=(34,23,37))
        d.polygon([(317,406),(396,454),(497,405),(464,469),(347,469)],
                  fill=(34,23,37))
        hp=max(0,info.get("hp",450))
        d.rounded_rectangle((119,574,739,600),radius=10,fill=(30,20,32))
        if hp:
            d.rounded_rectangle((119,574,119+round(620*hp/450),600),
                                radius=9,fill=(255,145,70))
        _write(im,(432,623),f"{hp} / 450 PV",29,GOLD,anchor="mm")


def scene_file(kind,stage, *, lines=(), info=None):
    """Fresh image for every interaction. No duplicate title in Discord embeds."""
    if kind not in PALETTE:
        raise ValueError(kind)
    info=info or {}
    img=_base(kind)
    titles={"ghosthunt":"LA CHASSE AUX FANTÔMES",
            "pumpkin":"LA CITROUILLE MYSTÉRIEUSE",
            "expedition":"L'EXPÉDITION MAUDITE",
            "duel":"LE DUEL DES OMBRES",
            "boss":"LE ROI DES CITROUILLES"}
    d=ImageDraw.Draw(img)
    _write(img,(73,96),titles[kind],
           _fit(titles[kind],1090,size=57,min_size=39),GOLD,glow=4)
    _art(img,kind,stage,info)
    shade=PALETTE[kind][2]
    d.rounded_rectangle((790,191,1200,606),radius=24,
                        fill=(14,11,25,244),outline=(*shade,190),width=3)
    label={"start":"CHOISIS TON ACTION","crack":"OUVRE LE TRÉSOR",
           "route":"CHOISIS TON CHEMIN","challenge":"PRÉPARE-TOI",
           "fight":"COMBAT EN COURS","result":"LE VERDICT",
           "expired":"PARTIE TERMINÉE"}.get(stage,"L'AVENTURE")
    _write(img,(818,214),label,27,shade)
    d.line((815,264,1170,264),fill=(*shade,160),width=2)
    # Fit and wrap each message in the right panel instead of clipping.
    yy=297
    for line in lines[:7]:
        if not line:
            yy+=18
            continue
        words=str(line).split()
        row=""
        for word in words:
            candidate=(row+" "+word).strip()
            bbox=d.textbbox((0,0),candidate,font=_font(23))
            if bbox[2]-bbox[0]>340 and row:
                _write(img,(813,yy),row,23,TEXT)
                yy+=35
                row=word
            else:
                row=candidate
        if row:
            _write(img,(813,yy),row,23,TEXT)
            yy+=51
        if yy>579:
            break
    _write(img,(87,645),"5 AVENTURES DISTINCTES  •  BONBONS VIRTUELS",
           20,FADE)
    output=BytesIO()
    img.convert("RGB").save(output,"JPEG",quality=85,optimize=True)
    return discord.File(BytesIO(output.getvalue()),filename=FILE)


def _gallery():
    return discord.ui.MediaGallery(discord.MediaGalleryItem(media=URI))


class SoloAdventure(discord.ui.LayoutView):
    kind=""
    def __init__(self,bot,guild_id,owner_id):
        super().__init__(timeout=180)
        self.bot=bot
        self.guild_id=guild_id
        self.owner_id=owner_id
        self.message=None
        self.stage="start"
        self.lines=[]
        self.info={}
        self._lock=asyncio.Lock()
        self.render()

    async def interaction_check(self,i):
        if (not i.guild or i.guild.id!=self.guild_id
                or i.user.id!=self.owner_id or i.user.bot):
            await fail(i,"Cette aventure est à un autre joueur. Lance ta propre commande.")
            return False
        return True

    def make_button(self,label,icon,callback,style=discord.ButtonStyle.secondary):
        button=discord.ui.Button(label=label,emoji=button_icon(icon),style=style)
        button.callback=callback
        return button

    def controls(self):
        return []

    def render(self):
        self.clear_items()
        self.add_item(_gallery())
        buttons=self.controls()
        if buttons:
            self.add_item(discord.ui.ActionRow(*buttons[:5]))

    def art(self):
        return scene_file(self.kind,self.stage,lines=self.lines,info=self.info)

    async def update(self,i):
        self.render()
        await i.response.edit_message(
            view=self,attachments=[self.art()],
            allowed_mentions=discord.AllowedMentions.none())

    async def on_timeout(self):
        async with self._lock:
            if self.stage in ("result","expired"):
                return
            self.stage="expired"
            self.lines=["Le portail s'est refermé.","Relance la commande pour jouer."]
            self.render()
            for row in self.children:
                if isinstance(row,discord.ui.ActionRow):
                    for button in row.children:
                        button.disabled=True
            if self.message:
                try:
                    await self.message.edit(view=self,attachments=[self.art()],
                                            allowed_mentions=discord.AllowedMentions.none())
                except (discord.HTTPException,discord.NotFound):
                    LOG.debug("Expired solo adventure panel disappeared")
            self.stop()


class GhostHuntView(SoloAdventure):
    kind="ghosthunt"
    PLACES=("Vieille tombe","Chapelle","Arbre hanté")
    def __init__(self,bot,guild_id,owner_id):
        self.hidden=random.randrange(3)
        super().__init__(bot,guild_id,owner_id)
        self.lines=["Une présence traverse le brouillard...",
                    f"Des traces brillent près de : {self.PLACES[self.hidden]}.",
                    "Trouve sa cachette !"]

    def controls(self):
        if self.stage!="start": return []
        controls=[]
        for n,name in enumerate(self.PLACES):
            async def pick(i,place=n):
                await self.search(i,place)
            controls.append(self.make_button(
                name,"ghost",pick,discord.ButtonStyle.primary))
        return controls

    async def search(self,i,place):
        async with self._lock:
            if self.stage!="start":
                return await fail(i,"Cette chasse est déjà terminée.")
            wait=self.bot.store.cooldown(self.guild_id,self.owner_id,"hunt",300)
            if wait: return await fail(i,wait_text(wait))
            caught=(place==self.hidden and random.random()>=0.28)
            amount=0
            if caught:
                name,low,high=random.choices(HUNTS,weights=[45,30,20,5])[0]
                amount=random.randint(low,high)
                self.bot.store.award(self.guild_id,self.owner_id,amount,ghosts=1)
                result=name.replace("👻","").replace("🦇","").replace("💀","").replace("✨","").strip()
                self.lines=[f"{result} capturé !",f"+{amount} bonbons",
                            "Le piège spectral s'est refermé."]
            else:
                self.lines=["Le fantôme s'est échappé !","0 bonbon",
                            "Observe les traces la prochaine fois."]
            self.stage="result"
            self.info={"caught":caught}
            await self.update(i)
            self.stop()


class PumpkinView(SoloAdventure):
    kind="pumpkin"
    def __init__(self,bot,guild_id,owner_id):
        self.choice=None
        self.cracks=0
        super().__init__(bot,guild_id,owner_id)
        self.lines=["Trois citrouilles étranges...",
                    "Choisis-en une, puis ouvre-la en trois coups.",
                    "Le trésor reste inconnu !"]

    def controls(self):
        if self.stage=="start":
            buttons=[]
            for j,name in enumerate(("Ambrée","Violette","Maudite")):
                async def pick(i,chosen=j): await self.select(i,chosen)
                buttons.append(self.make_button(name,"pumpkin",pick,
                               discord.ButtonStyle.primary if j==1
                               else discord.ButtonStyle.secondary))
            return buttons
        if self.stage=="crack":
            return [self.make_button(f"Frapper ({self.cracks}/3)","sword",
                                     self.hit,discord.ButtonStyle.success),
                    self.make_button("Changer de citrouille","broom",self.back)]
        return []

    async def select(self,i,chosen):
        async with self._lock:
            if self.stage!="start": return await fail(i,"Choix déjà effectué.")
            self.choice=chosen
            self.info={"choice":chosen,"cracks":0}
            self.lines=["La citrouille tremble...", "Frappe trois fois pour l'ouvrir.",
                        "Aucun bonbon n'est encore dépensé."]
            self.stage="crack"
            await self.update(i)

    async def back(self,i):
        async with self._lock:
            if self.stage!="crack":return await fail(i,"Impossible de revenir.")
            self.stage="start"
            self.choice=None
            self.cracks=0
            self.info={}
            self.lines=["Choisis une citrouille.","Frappe trois fois pour révéler son trésor."]
            await self.update(i)

    async def hit(self,i):
        async with self._lock:
            if self.stage!="crack":return await fail(i,"Cette citrouille est déjà ouverte.")
            if self.cracks==2:
                wait=self.bot.store.cooldown(self.guild_id,self.owner_id,"pumpkin",600)
                if wait:return await fail(i,wait_text(wait))
            self.cracks+=1
            self.info={"choice":self.choice,"cracks":self.cracks}
            if self.cracks<3:
                self.lines=[f"CRAC ! {self.cracks}/3 coups.",
                            "Encore un effort, le trésor approche !"]
            else:
                kind=random.choices(["simple","rare","legendary","empty"],
                                    [56,31,5,8])[0]
                amount={"simple":random.randint(30,90),
                        "rare":random.randint(100,220),
                        "legendary":random.randint(350,650),"empty":0}[kind]
                player=self.bot.store.award(self.guild_id,self.owner_id,amount,pumpkins=1)
                label={"simple":"Friandises !","rare":"Trésor rare !",
                       "legendary":"Citrouille légendaire !","empty":"Citrouille vide."}[kind]
                self.lines=[label,f"+{amount} bonbons",
                            f"Sac : {player['candies']} bonbons"]
                self.stage="result"
            await self.update(i)
            if self.stage=="result":self.stop()


class ExpeditionView(SoloAdventure):
    kind="expedition"
    PATHS=("crypte","grenier","cave")
    def __init__(self,bot,guild_id,owner_id):
        self.path=None
        super().__init__(bot,guild_id,owner_id)
        self.lines=["La maison ouvre trois passages.",
                    "Chaque chemin cache un risque différent.",
                    "Choisis ton itinéraire."]

    def controls(self):
        if self.stage=="start":
            buttons=[]
            for n,(label,icon) in enumerate((("Crypte","skull"),("Grenier","bat"),
                                              ("Cave","candle"))):
                async def select(i,idx=n):await self.choose_path(i,idx)
                buttons.append(self.make_button(label,icon,select,
                         discord.ButtonStyle.primary if n==0 else
                         discord.ButtonStyle.secondary))
            return buttons
        if self.stage=="route":
            return [self.make_button("Avancer prudemment","key",
                                     self.cautious,discord.ButtonStyle.success),
                    self.make_button("Foncer vers le trésor","sword",self.rush,
                                     discord.ButtonStyle.danger),
                    self.make_button("Changer de chemin","map",self.back)]
        return []

    async def choose_path(self,i,path):
        async with self._lock:
            if self.stage!="start":return await fail(i,"Chemin déjà choisi.")
            self.path=self.PATHS[path]
            self.stage="route"
            self.lines=[f"Direction : {self.path.title()}",
                        "Prudence : moins de pièges, butin plus modeste.",
                        "Foncer : gros butin, risque accru !"]
            await self.update(i)

    async def back(self,i):
        async with self._lock:
            if self.stage!="route":return await fail(i,"Ce passage est fermé.")
            self.stage="start"
            self.path=None
            self.lines=["Rechoisis ton passage.","Aucun bonbon n'a été consommé."]
            await self.update(i)

    async def cautious(self,i):await self.finish(i,False)
    async def rush(self,i):await self.finish(i,True)

    async def finish(self,i,rush):
        async with self._lock:
            if self.stage!="route":return await fail(i,"L'exploration est terminée.")
            wait=self.bot.store.cooldown(self.guild_id,self.owner_id,
                                         "expedition",600)
            if wait:return await fail(i,wait_text(wait))
            danger={"crypte":.30,"grenier":.20,"cave":.12}[self.path]
            danger=min(.85,danger*(1.45 if rush else .55))
            trapped=random.random()<danger
            if trapped:
                amount=-random.randint(10,40)
                self.lines=["Un piège s'est déclenché !",
                            f"{amount} bonbons","Le manoir reprend son tribut."]
            else:
                amount=random.randint(70,160)+(40 if self.path=="crypte" else 0)
                amount=round(amount*(1.2 if rush else .8))
                self.lines=["Un coffre ancien !",f"+{amount} bonbons",
                            "Tu repars avec ton trésor."]
            self.bot.store.award(self.guild_id,self.owner_id,
                                 amount,expeditions=1)
            self.stage="result"
            await self.update(i)
            self.stop()


class DuelView(discord.ui.LayoutView):
    kind="duel"
    def __init__(self,bot,guild_id,challenger,opponent,names):
        super().__init__(timeout=180)
        self.bot=bot
        self.guild_id=guild_id
        self.challenger=challenger
        self.opponent=opponent
        self.names=names
        self.players=[challenger,opponent]
        self.hp=[100,100]
        self.guard=[False,False]
        self.turn=0
        self.moves=0
        self.stage="challenge"
        self.message=None
        self.finished=False
        self.lines=["Un duel t'attend.",
                    f"{names[0][:14]} défie {names[1][:14]}.",
                    "Accepte pour commencer !"]
        self._lock=asyncio.Lock()
        self.render()

    def render(self):
        self.clear_items()
        self.add_item(_gallery())
        controls=[]
        if self.stage=="challenge":
            controls=[self._button("Accepter","duel",self.accept,discord.ButtonStyle.success),
                      self._button("Refuser","cross",self.refuse)]
        elif self.stage=="fight":
            controls=[self._button("Attaquer","sword",self.attack,discord.ButtonStyle.danger),
                      self._button("Se défendre","shield",self.defend),
                      self._button("Sortilège","wand",self.cast,discord.ButtonStyle.primary)]
        if controls:self.add_item(discord.ui.ActionRow(*controls))

    def _button(self,label,icon,callback,style=discord.ButtonStyle.secondary):
        b=discord.ui.Button(label=label,emoji=button_icon(icon),style=style)
        b.callback=callback
        return b

    def art(self):
        return scene_file(self.kind,
                          "fight" if self.stage=="fight" else
                          "result" if self.finished else "start",
                          info={"names":self.names,"hp":self.hp},
                          lines=self.lines)

    async def interaction_check(self,i):
        if not i.guild or i.guild.id!=self.guild_id or i.user.id not in self.players:
            await fail(i,"Seuls les deux combattants peuvent interagir.")
            return False
        return True

    async def update(self,i):
        self.render()
        await i.response.edit_message(
            view=self,attachments=[self.art()],
            allowed_mentions=discord.AllowedMentions.none())

    async def accept(self,i):
        async with self._lock:
            if self.stage!="challenge":return await fail(i,"Duel déjà lancé.")
            if i.user.id!=self.opponent:
                return await fail(i,"Seul l'adversaire peut accepter.")
            self.stage="fight"
            self.lines=["Le combat commence !",
                        f"C'est au tour de {self.names[0][:20]}.",
                        "Choisis Attaquer, Défendre ou Sortilège."]
            await self.update(i)

    async def refuse(self,i):
        async with self._lock:
            if self.stage!="challenge":return await fail(i,"Le duel est déjà lancé.")
            if i.user.id!=self.opponent:return await fail(i,"Seul l'adversaire peut refuser.")
            self.stage="result"
            self.finished=True
            self.lines=["L'adversaire a refusé.","Aucun bonbon attribué."]
            await self.update(i)
            self.stop()

    async def attack(self,i):await self.move(i,"attack")
    async def defend(self,i):await self.move(i,"guard")
    async def cast(self,i):await self.move(i,"spell")

    async def move(self,i,choice):
        async with self._lock:
            if self.stage!="fight":return await fail(i,"Le combat est terminé.")
            turn=self.turn
            if i.user.id!=self.players[turn]:
                return await fail(i,"C'est au tour de l'autre combattant.")
            other=1-turn
            if choice=="guard":
                self.guard[turn]=True
                msg=f"{self.names[turn][:15]} prépare un bouclier."
            else:
                strength=random.randint(17,32) if choice=="attack" else random.randint(23,43)
                if choice=="spell" and random.random()<.22:
                    strength=0
                if self.guard[other]:
                    strength=math.ceil(strength*.45)
                    self.guard[other]=False
                self.hp[other]=max(0,self.hp[other]-strength)
                msg=f"{self.names[turn][:15]} inflige {strength} dégâts."
            self.moves+=1
            if self.hp[other]==0 or self.moves>=10:
                winner=turn if self.hp[other]==0 else (
                    0 if self.hp[0]>self.hp[1] else
                    1 if self.hp[1]>self.hp[0] else random.randrange(2))
                loser=1-winner
                self.bot.store.award(self.guild_id,self.players[winner],
                                     120,duel_wins=1)
                self.bot.store.award(self.guild_id,self.players[loser],
                                     30,duel_losses=1)
                self.lines=[f"{self.names[winner][:16]} gagne !",
                            f"{msg}",
                            "+120 bonbons gagnant / +30 participant"]
                self.stage="result"
                self.finished=True
            else:
                self.turn=other
                self.lines=[msg,f"Au tour de {self.names[other][:20]}.",
                            f"Manche {self.moves+1} / 10"]
            await self.update(i)
            if self.finished:self.stop()

    async def on_timeout(self):
        async with self._lock:
            if self.finished:return
            self.finished=True
            self.stage="result"
            self.lines=["Duel expiré.","Aucune récompense distribuée."]
            self.render()
            if self.message:
                try:
                    await self.message.edit(view=self,attachments=[self.art()])
                except (discord.HTTPException,discord.NotFound):pass
            self.stop()


class BossView(discord.ui.LayoutView):
    kind="boss"
    def __init__(self,bot,guild_id):
        super().__init__(timeout=300)
        self.bot=bot
        self.guild_id=guild_id
        self.hp=450
        self.damage={}
        self.hits={}
        self.last={}
        self.finished=False
        self.message=None
        self.stage="fight"
        self.lines=["Le monstre surgit de la lave !",
                    "3 attaques par joueur · 10 s entre deux.",
                    "Plusieurs membres peuvent combattre."]
        self._lock=asyncio.Lock()
        self.render()

    def render(self):
        self.clear_items()
        self.add_item(_gallery())
        if not self.finished:
            controls=[]
            for name,icon,style,move in (
                ("Épée","sword",discord.ButtonStyle.primary,"sword"),
                ("Magie","wand",discord.ButtonStyle.success,"magic"),
                ("Attaque risquée","fire",discord.ButtonStyle.danger,"risk")
            ):
                async def callback(i,kind=move):await self.attack(i,kind)
                b=discord.ui.Button(label=name,emoji=button_icon(icon),style=style)
                b.callback=callback
                controls.append(b)
            self.add_item(discord.ui.ActionRow(*controls))

    def art(self):return scene_file("boss",self.stage,info={"hp":self.hp},
                                    lines=self.lines)

    async def attack(self,i,move):
        async with self._lock:
            if self.finished:return await fail(i,"Le boss a déjà disparu.")
            if not i.guild or i.guild.id!=self.guild_id or i.user.bot:
                return await fail(i,"Ce combat est réservé aux joueurs du serveur.")
            uid=i.user.id
            now=time.monotonic()
            if self.hits.get(uid,0)>=3:
                return await fail(i,"Tu as déjà effectué tes trois attaques.")
            if now-self.last.get(uid,-1e9)<10:
                return await fail(i,"Attends 10 secondes entre deux attaques.")
            damage=(random.randint(22,42) if move=="sword" else
                    random.randint(30,60) if move=="magic" else
                    0 if random.random()<.28 else random.randint(40,82))
            # Actual applied damage can never exceed the remaining HP.
            damage=min(self.hp,damage)
            self.hp-=damage
            self.hits[uid]=self.hits.get(uid,0)+1
            self.last[uid]=now
            self.damage[uid]=self.damage.get(uid,0)+damage
            if damage:self.bot.store.award(self.guild_id,uid,boss_damage=damage)
            phase=("PHASE 3 : FURIE" if self.hp<=150 else
                   "PHASE 2 : FEU" if self.hp<=300 else
                   "PHASE 1 : ÉVEIL")
            self.lines=[f"{phase}",f"{i.user.display_name[:18]} : {damage} dégâts.",
                        f"{self.hp} / 450 PV restants."]
            if self.hp<=0:
                self.finished=True
                self.stage="result"
                for participant in self.damage:
                    self.bot.store.award(self.guild_id,participant,150)
                self.bot.active_bosses.pop(self.guild_id,None)
                self.lines=["LE BOSS EST VAINCU !",
                            f"{len(self.damage)} participants récompensés.",
                            "+150 bonbons chacun."]
            self.render()
            await i.response.edit_message(view=self,attachments=[self.art()],
                                          allowed_mentions=discord.AllowedMentions.none())
            if self.finished:self.stop()

    async def on_timeout(self):
        async with self._lock:
            if self.finished:return
            self.finished=True
            self.stage="expired"
            self.bot.active_bosses.pop(self.guild_id,None)
            self.lines=["Le boss disparaît dans la brume.",
                        "Aucune récompense de victoire."]
            self.render()
            if self.message:
                try:
                    await self.message.edit(view=self,attachments=[self.art()])
                except (discord.NotFound,discord.HTTPException):pass
            self.stop()


async def send_adventure(i,view,*,mention_user=None):
    if not i.app_permissions.attach_files:
        return await fail(i,"Autorise « Joindre des fichiers » au bot pour jouer.")
    await i.response.send_message(view=view,file=view.art(),ephemeral=False,
                                  allowed_mentions=(
                                      discord.AllowedMentions(users=[mention_user])
                                      if mention_user else discord.AllowedMentions.none()))
    view.message=await i.original_response()
