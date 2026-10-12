"""/boutique — Morgane's shop: consumables, titles and profile themes."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import NotEnough
from ..emojis import E
from ..ui import GameView, Panel, nav, relative

INSTANT = {"luck", "scroll"}  # applied right away instead of going to the bag


class ShopView(GameView):
    banner_key = "shop"
    owner_hint = "Ouvre ta propre boutique avec /boutique."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=600)
        self.flash = ""

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        bal = self.store.candies(g, u)
        items = self.store.items(g, u)
        owned = self.store.owned(g, u)
        player = self.store.player(g, u)
        p = Panel("purple").banner(self.banner_key)
        p.title("La boutique de Morgane", icon="witch", thumb=E.url("witch"),
                body=f"« Approche, approche… J'ai tout ce qu'il faut pour terroriser tes rivaux. »\n"
                     f"Tu as **{config.fmt(bal)}** {E.candy}")
        if self.flash:
            p.text(self.flash)
            self.flash = ""
        p.sep()
        lines = []
        for key, it in config.SHOP.items():
            qty = items.get(key, 0)
            lines.append(f"{E(it['emoji'])} **{it['name']}** — {config.fmt(it['price'])} {E.candy}"
                         + (f" · tu en as {qty}" if qty else "") + f"\n-# {it['desc']}")
        p.text("### Objets\n" + "\n".join(lines))
        p.sep()
        titles = [f"{E.check if 'title:' + k in owned else E.scroll} *{t['name']}* — {config.fmt(t['price'])}"
                  for k, t in config.TITLES_SHOP.items()]
        themes = [f"{E.check if 'theme:' + k in owned or not t['price'] else E.star} {t['name']}"
                  + (f" — {config.fmt(t['price'])}" if t["price"] else "")
                  for k, t in config.CARD_THEMES.items()]
        p.text("### Titres\n" + " · ".join(titles) + "\n### Couleurs de carte de profil\n" + " · ".join(themes))
        p.sep()
        buy = discord.ui.Select(placeholder="Acheter un objet…", options=[
            discord.SelectOption(label=f"{it['name']} — {it['price']}", value=f"item:{k}", emoji=E.partial(it["emoji"]),
                                 description=it["desc"][:100])
            for k, it in config.SHOP.items()])
        buy.callback = self._buy
        p.row(buy)
        cosm = []
        for k, t in config.TITLES_SHOP.items():
            if "title:" + k not in owned:
                cosm.append(discord.SelectOption(label=f"Titre « {t['name']} » — {config.fmt(t['price'])}",
                                                 value=f"title:{k}", emoji=E.partial("scroll")))
        for k, t in config.CARD_THEMES.items():
            if t["price"] and "theme:" + k not in owned:
                cosm.append(discord.SelectOption(label=f"Couleur {t['name']} — {config.fmt(t['price'])}",
                                                 value=f"theme:{k}", emoji=E.partial("star")))
        if cosm:
            sel = discord.ui.Select(placeholder="Acheter un titre ou une couleur…", options=cosm[:25])
            sel.callback = self._buy
            p.row(sel)
        equip = [discord.SelectOption(label="Titre de niveau (automatique)", value="title:", emoji=E.partial("star"),
                                      default=not player["title"])]
        for k, t in config.TITLES_SHOP.items():
            if "title:" + k in owned:
                equip.append(discord.SelectOption(label=f"Titre : {t['name']}", value=f"title:{k}",
                                                  emoji=E.partial("scroll"), default=player["title"] == k))
        for k, t in config.CARD_THEMES.items():
            if not t["price"] or "theme:" + k in owned:
                equip.append(discord.SelectOption(label=f"Couleur : {t['name']}", value=f"theme:{k}",
                                                  emoji=E.partial("star"), default=player["theme"] == k))
        sel = discord.ui.Select(placeholder="Équiper…", options=equip[:25])
        sel.callback = self._equip
        p.row(sel)
        p.row(nav("cards", self.owner_id, "Mes cartes", "gift"), nav("profile", self.owner_id, "Profil", "pumpkin_lit"))
        p.footer(self.footer())
        return p

    async def _buy(self, interaction):
        kind, key = interaction.data["values"][0].split(":", 1)
        g, u = self.guild_id, self.owner_id
        try:
            if kind == "item":
                it = config.SHOP[key]
                if key in INSTANT:
                    self.store.spend(g, u, it["price"], f"boutique:{key}")
                    if key == "luck":
                        until = self.store.add_effect(g, u, "luck", 1800)
                        self.flash = f"{E.potion_gold} Gains **×2** jusqu'à {relative(until)} !"
                    else:
                        self.store.bump(g, u, "quiz_bonus", amount=5)
                        self.flash = f"{E.scroll} **+5 questions** de quiz aujourd'hui !"
                else:
                    self.store.buy(g, u, it["price"], item=key, reason=f"boutique:{key}")
                    self.flash = f"{E(it['emoji'])} **{it['name']}** ajouté à ton sac !"
            elif kind == "title":
                t = config.TITLES_SHOP[key]
                self.store.buy(g, u, t["price"], thing=f"title:{key}", reason="titre")
                self.store.set_field(g, u, "title", key)
                self.flash = f"{E.scroll} Tu portes désormais le titre **{t['name']}** !"
            else:
                t = config.CARD_THEMES[key]
                self.store.buy(g, u, t["price"], thing=f"theme:{key}", reason="theme")
                self.store.set_field(g, u, "theme", key)
                self.flash = f"{E.star} Ta carte de profil passe en couleur **{t['name']}** !"
        except NotEnough:
            self.flash = f"{E.cross} Pas assez de bonbons… Morgane ne fait pas crédit."
        except ValueError:
            self.flash = f"{E.check} Tu possèdes déjà cet article."
        await self.refresh(interaction)

    async def _equip(self, interaction):
        kind, key = interaction.data["values"][0].split(":", 1)
        g, u = self.guild_id, self.owner_id
        if kind == "title":
            if key and not self.store.owns(g, u, f"title:{key}"):
                return await self.refresh(interaction)
            self.store.set_field(g, u, "title", key or None)
            self.flash = f"{E.check} Titre équipé."
        else:
            if config.CARD_THEMES[key]["price"] and not self.store.owns(g, u, f"theme:{key}"):
                return await self.refresh(interaction)
            self.store.set_field(g, u, "theme", key)
            self.flash = f"{E.check} Couleur équipée."
        await self.refresh(interaction)


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["shop"] = self.open

    async def open(self, interaction, edit=False):
        await ShopView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="boutique", description="🧙 La boutique de Morgane : jokers, potions, titres, couleurs")
    @app_commands.guild_only()
    async def boutique(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Shop(bot))
