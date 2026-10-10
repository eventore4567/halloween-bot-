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
    y = 340
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
    _write(img, (x, y+222), f"PORTE {number+1}", 34, COPPER if chosen else CREAM,
           anchor="mm")
    _write(img, (x, y+260), caption, 24, LILAC, anchor="mm")


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
        extra={"selected":self.selected, "result":self.result}
        if self.stage=="inventory":
            from .content import ITEMS
            names={"legendary_pumpkin":RARE_NAME}
            inv=self.bot.store.inventory(self.guild_id,self.owner_id)
            extra["inventory"]=[
                ((names.get(x["item"]) or ITEMS[x["item"]][0].split(" ",1)[-1])
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
