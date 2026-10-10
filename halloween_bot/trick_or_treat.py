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
from io import BytesIO

import discord
from PIL import Image, ImageDraw, ImageFilter

from .common import button_icon, fail, wait_text
from .scene import _lettering, _fit

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


def _write(img, xy, value, size, color=CREAM, *, anchor=None, glow=0, serif=False):
    _lettering(img, xy, str(value), size, color=color, anchor=anchor,
               glow=glow, serif=serif)


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
    d.ellipse((1049, 63, 1170, 184), fill=(246, 201, 157))
    d.ellipse((1097, 27, 1200, 165), fill=(22, 18, 43))
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
    y = 310
    _, caption, hue = DOORS[number]
    d = ImageDraw.Draw(img)
    # Carved arch: a pointed roof plus a glowing wooden entrance.
    frame = (x-126, y-75, x+126, y+246)
    if chosen:
        halo = Image.new("RGBA", img.size)
        h = ImageDraw.Draw(halo)
        h.ellipse((x-167, y-85, x+167, y+290), fill=(*hue, 105))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(35)))
        d = ImageDraw.Draw(img)
    d.rounded_rectangle(frame, radius=42,
                        fill=(39, 21, 37, 255),
                        outline=(*hue, 255), width=9 if chosen else 5)
    d.polygon([(x-124,y+32), (x,y-160), (x+124,y+32)],
              fill=(28, 18, 36), outline=(*hue,255), width=6)
    d.rounded_rectangle((x-96, y-32, x+96, y+213), radius=23,
                        fill=(64, 29, 26) if number!=2 else (39, 26, 78),
                        outline=(*hue, 225), width=3)
    d.line((x,y-26,x,y+208),fill=(*hue,110),width=3)
    for yy in (y+17,y+65,y+113,y+163):
        d.line((x-85,yy,x+85,yy),fill=(*hue,45),width=2)
    d.ellipse((x+47,y+90,x+64,y+107),fill=BRIGHT)
    d.ellipse((x+52,y+95,x+59,y+102),fill=(66,38,38))
    for dx in (-89,89):
        d.ellipse((x+dx-5,y+180,x+dx+5,y+191),fill=(*hue,255))
    _write(img, (x, y+270), f"PORTE {number+1}", 34, COPPER if chosen else CREAM,
           anchor="mm")
    _write(img, (x, y+311), caption, 24, LILAC, anchor="mm")


def _header(img, title, kicker):
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((60, 49, 800, 200), radius=26,
                        fill=(15, 10, 30, 215),
                        outline=(183, 104, 91, 150), width=3)
    _write(img, (93, 72), "CRYPT CUP    /    HALLOWEEN", 25, LILAC)
    sz = _fit(title, 680, size=66, min_size=41, serif=True)
    _write(img, (91, 112), title, sz, COPPER, glow=5, serif=True)
    _write(img, (95, 181), kicker, 24, CREAM)


def _status(img, candies, streak, *, extra="CHOISIS UNE PORTE"):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((54, 614, 1225, 661), radius=12,
                        fill=(18, 13, 36, 243),
                        outline=(192, 108, 93, 120), width=2)
    _write(img, (81, 624), f"SAC   {candies:,} BONBONS", 22, BRIGHT)
    _write(img, (477, 624), f"SERIE   {streak} VICTOIRE(S)", 22, CREAM)
    _write(img, (845, 624), extra, 21, LILAC)


def _information(img, title, lines, *, selected=None, hue=COPPER):
    _header(img, title, "LE MANOIR GARDE SES SECRETS")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((71, 239, 1205, 580),radius=22,
                        fill=(19,12,33,239),outline=(*hue,165),width=3)
    for j, line in enumerate(lines[:6]):
        if not line:
            continue
        label=str(line)
        size=_fit(label, 1010, size=42 if j == 0 else 33, min_size=24)
        _write(img,(110,277+j*50),label,size,hue if j==0 else CREAM)


def banner_bytes(stage, candies, streak, *, selected=None, result=None,
                 inventory=(), leaders=(), remaining=0):
    img = _background()
    if stage == "intro":
        _header(img, "LE MANOIR HANTE", "TROIS PORTES • UN SEUL DESTIN")
        _door(img, 249, number=0)
        _door(img, 640, number=1)
        _door(img, 1030, number=2)
        _status(img, candies, streak)
    elif stage == "opening":
        _header(img, "LA PORTE S'OUVRE...", "UN BRUIT ETRANGE RESONNE DANS L'OMBRE")
        _door(img, 640, number=selected or 0, chosen=True)
        _write(img,(235,477),"QU'Y A-T-IL DERRIERE ?", 34, BRIGHT)
        _status(img, candies, streak, extra="REVELATION...")
    elif stage == "result" and result:
        kind=result["kind"]
        data={
            "treat":("BONBONS DECOUVERTS", "Le manoir t'offre des friandises.",MINT),
            "jackpot":("TRESOR LEGENDAIRE", "Une citrouille magique t'attend !",BRIGHT),
            "trick":("UN FANTOME ATTAQUE", "Le spectre s'enfuit avec ton butin.",PERIL),
            "nothing":("LE MANOIR EST VIDE", "Aucun bonbon cette fois.",LILAC),
        }
        title, subtitle, hue=data[kind]
        amount=result["amount"]
        amount_text=f"+{amount:,} BONBONS" if amount>0 else (
            f"{amount:,} BONBONS" if amount<0 else "0 BONBON")
        lines=[
            subtitle, amount_text,
            "OBJET RARE : CITROUILLE LEGENDAIRE" if result["rare"]
                else "TON AVENTURE EST TERMINEE",
            f"PROCHAINE PARTIE DISPONIBLE DANS 15 MIN",
        ]
        _information(img,title,lines,hue=hue)
        _status(img,result["candies"],result["streak"],extra=f"PORTE {selected+1}")
    elif stage=="inventory":
        lines=["TES OBJETS COLLECTIONNES"]
        lines += [f"{name[:40]}    x{qty}" for name,qty in inventory[:5]]
        if not inventory:
            lines.append("AUCUN OBJET POUR LE MOMENT")
        _information(img,"LE SAC DU CHASSEUR",lines)
        _status(img,candies,streak,extra="INVENTAIRE")
    elif stage=="leaderboard":
        lines=["LES 5 MEILLEURS CHASSEURS"]
        lines += [f"{rank}. {name[:24]}  -  {score:,} BONBONS"
                  for rank, name, score in leaders[:5]]
        if not leaders:
            lines.append("AUCUN JOUEUR CLASSE")
        _information(img,"LES LEGENDES",lines,hue=BRIGHT)
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
        extra={"selected":self.selected, "result":self.result}
        if self.stage=="inventory":
            from .content import ITEMS
            names={"legendary_pumpkin":RARE_NAME}
            inv=self.bot.store.inventory(self.guild_id,self.owner_id)
            extra["inventory"]=[
                (names.get(x["item"], ITEMS.get(x["item"],(x["item"],))[0]),
                 x["quantity"]) for x in inv
            ]
        elif self.stage=="leaderboard":
            guild=self.bot.get_guild(self.guild_id)
            rows=self.bot.store.ranking(self.guild_id,"candies",5)
            extra["leaders"]=[
                (n,
                 guild.get_member(x["user_id"]).display_name
                 if guild and guild.get_member(x["user_id"])
                 else f"Joueur {x['user_id']}",
                 x["score"]) for n,x in enumerate(rows,1)
            ]
        return banner_file(self.stage,candies,streak,**extra)

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
            for i, emoji in enumerate(("key","pumpkin","ghost")):
                async def choose(interaction, index=i):
                    await self.choose(interaction,index)
                buttons.append(self._button(
                    f"Porte {i+1}",emoji,
                    (discord.ButtonStyle.primary if i==2
                     else discord.ButtonStyle.success if i==1
                     else discord.ButtonStyle.secondary),
                    choose,
                ))
            buttons.extend(self._navigation())
        elif self.stage=="opening":
            buttons.append(self._button(
                "La porte s'ouvre...", "clock",
                discord.ButtonStyle.secondary,self._nothing,disabled=True
            ))
        elif self.stage=="result":
            buttons.extend([
                self._button("Rejouer","pumpkin",discord.ButtonStyle.success,
                             self.replay),
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
        await interaction.response.edit_message(
            view=self,attachments=[self._view_file()],
            allowed_mentions=discord.AllowedMentions.none(),
        )

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
            self.stage="expired"
            self._draw()
            if self.message is not None:
                try:
                    await self.message.edit(
                        view=self,attachments=[self._view_file()],
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.NotFound,discord.HTTPException):
                    LOG.debug("Cannot mark expired trick-or-treat view",exc_info=True)
            self.stop()
