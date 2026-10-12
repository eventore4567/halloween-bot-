"""/echange — trade cursed cards (and candies) with another member, with an animated swap."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import trade as art
from ..content.games import CARD, CARDS, RARITIES
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, button, image_file, notice, relative, stable_message
from .cards import collection_bonus

MAX_CARDS = 3
OFFER_TIME = 300
XP_TRADES_PER_DAY = 3  # trades that still give XP each day (no farming by trading back and forth)
GIF_NAME, PNG_NAME = "echange.gif", "echange.png"


def card_label(key: str, count: int) -> str:
    c = CARD[key]
    return f"{c['name']} ({RARITIES[c['rarity']]['name']})" + (f" ×{count}" if count > 1 else "")


class TradeView(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int, a, b, candies: int = 0):
        super().__init__(timeout=OFFER_TIME + 30)
        self.bot, self.store, self.guild_id = bot, bot.store, guild_id
        self.a, self.b, self.candies = a, b, candies
        self.give: list[str] = []
        self.take: list[str] = []
        self.state = "draft"
        self.note = ""
        self.lock = asyncio.Lock()
        self.message = None
        self.deadline = time.time() + OFFER_TIME
        self.render()

    # ----------------------------------------------------------------- render
    def _options(self, uid, chosen):
        cards = self.store.cards(self.guild_id, uid)
        keys = sorted(cards, key=lambda k: ("LERC".index(CARD[k]["rarity"]), CARD[k]["name"]))[:25]
        return [discord.SelectOption(label=card_label(k, cards[k])[:100], value=k, emoji=E.partial(CARD[k]["emoji"]),
                                     default=k in chosen) for k in keys]

    def render(self):
        self.clear_items()
        p = Panel("gold")
        if self.state in ("draft", "offer"):
            p.image(PNG_NAME)
        else:
            p.image(GIF_NAME if self.state == "done" else PNG_NAME)
        a, b = self.a, self.b
        give = ", ".join(f"{E(CARD[k]['emoji'])} **{CARD[k]['name']}**" for k in self.give) or "*rien*"
        take = ", ".join(f"{E(CARD[k]['emoji'])} **{CARD[k]['name']}**" for k in self.take) or "*rien*"
        extra = f" + **{config.fmt(self.candies)}** {E.candy}" if self.candies else ""
        summary = f"{a.mention} donne : {give}{extra}\n{b.mention} donne : {take}"
        if self.state == "draft":
            p.title("Préparer un échange", icon="gift",
                    body=f"{a.mention}, choisis les cartes que tu donnes et celles que tu veux de {b.mention} "
                         f"(jusqu'à {MAX_CARDS} de chaque côté), puis envoie ta proposition.\n{summary}")
            mine = self._options(a.id, self.give)
            theirs = self._options(b.id, self.take)
            if mine:
                s1 = discord.ui.Select(placeholder="Les cartes que tu donnes…", min_values=0,
                                       max_values=min(MAX_CARDS, len(mine)), options=mine)
                s1.callback = self._pick_give
                p.row(s1)
            if theirs:
                s2 = discord.ui.Select(placeholder=f"Les cartes que tu veux de {b.display_name}…"[:150], min_values=0,
                                       max_values=min(MAX_CARDS, len(theirs)), options=theirs)
                s2.callback = self._pick_take
                p.row(s2)
            if not mine and not theirs:
                p.text(f"{E.cross} Aucun de vous deux n'a de carte. Ouvrez des boosters avec `/cartes` !")
            p.row(button("Proposer l'échange", "check", "success", self._propose,
                         disabled=not (self.give or self.take) or (not self.give and not self.candies)),
                  button("Annuler", "cross", "danger", self._cancel))
        elif self.state == "offer":
            p.title(f"{a.display_name} te propose un échange !", icon="gift",
                    body=f"{summary}\n{E.hourglass} {b.mention}, réponds {relative(self.deadline)}")
            p.row(button("Accepter", "check", "success", self._accept), button("Refuser", "cross", "danger", self._refuse))
        elif self.state == "done":
            p.title("Échange conclu !", icon="sparkle", body=summary + (f"\n{self.note}" if self.note else ""))
        else:
            p.title({"refused": "Échange refusé", "cancel": "Échange annulé", "expired": "Proposition expirée",
                     "failed": "Échange impossible"}[self.state], icon="cross", body=self.note or summary)
        p.footer(f"{E.gift} Échange de cartes · `/echange @membre` · `/cartes` pour ta collection")
        self.add_item(p.container())

    async def picture(self) -> discord.File:
        data = await asyncio.to_thread(art.offer_png, self.a.display_name, self.b.display_name, self.give, self.take,
                                       self.candies)
        return image_file(data, PNG_NAME)

    async def update(self, interaction=None, attachments=None):
        self.render()
        kwargs = dict(view=self, allowed_mentions=NO_PINGS)
        if attachments is not None:
            kwargs["attachments"] = attachments
        try:
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.edit_message(**kwargs)
            elif interaction is not None:
                await interaction.edit_original_response(**kwargs)
            elif self.message:
                await self.message.edit(**kwargs)
        except discord.HTTPException:
            pass

    # ---------------------------------------------------------------- actions
    def _only(self, interaction, user) -> bool:
        return interaction.user.id == user.id

    async def _pick_give(self, interaction):
        if not self._only(interaction, self.a) or self.state != "draft":
            return await notice(interaction, "Seul celui qui propose l'échange choisit les cartes.")
        self.give = list(interaction.data.get("values", []))[:MAX_CARDS]
        await interaction.response.defer()
        await self.update(interaction, attachments=[await self.picture()])

    async def _pick_take(self, interaction):
        if not self._only(interaction, self.a) or self.state != "draft":
            return await notice(interaction, "Seul celui qui propose l'échange choisit les cartes.")
        self.take = list(interaction.data.get("values", []))[:MAX_CARDS]
        await interaction.response.defer()
        await self.update(interaction, attachments=[await self.picture()])

    async def _propose(self, interaction):
        if not self._only(interaction, self.a):
            return await notice(interaction, "Seul celui qui propose l'échange peut l'envoyer.")
        async with self.lock:
            if self.state != "draft":
                return await interaction.response.defer()
            self.state = "offer"
            self.deadline = time.time() + OFFER_TIME
            await self.update(interaction)
            if self.message is not None and hasattr(self.message, "reply"):
                try:  # ping the other member once, now that the offer is ready
                    await self.message.reply(f"{self.b.mention}, {self.a.display_name} te propose un échange !",
                                             allowed_mentions=discord.AllowedMentions(users=[self.b]))
                except discord.HTTPException:
                    pass

    async def _cancel(self, interaction):
        if not self._only(interaction, self.a):
            return await notice(interaction, "Seul celui qui propose l'échange peut l'annuler.")
        async with self.lock:
            if self.state not in ("draft", "offer"):
                return await interaction.response.defer()
            self.state = "cancel"
            self.stop()
            await self.update(interaction)

    async def _refuse(self, interaction):
        if interaction.user.id not in (self.a.id, self.b.id):
            return await notice(interaction, "Cet échange ne te concerne pas.")
        async with self.lock:
            if self.state != "offer":
                return await interaction.response.defer()
            self.state = "refused" if interaction.user.id == self.b.id else "cancel"
            self.stop()
            await self.update(interaction)

    async def _accept(self, interaction):
        if not self._only(interaction, self.b):
            return await notice(interaction, "Seul le destinataire peut accepter l'échange.")
        async with self.lock:
            if self.state != "offer":
                return await interaction.response.defer()
            if time.time() > self.deadline:
                self.state = "expired"
                self.stop()
                return await self.update(interaction)
            g = self.guild_id
            owned_before = {u.id: len(self.store.cards(g, u.id)) for u in (self.a, self.b)}
            if not self.store.trade(g, self.a.id, self.b.id, self.give, self.take, self.candies):
                self.state = "failed"
                self.note = f"{E.cross} L'un de vous n'a plus les cartes (ou les bonbons) promises."
                self.stop()
                return await self.update(interaction)
            lines = []
            for user in (self.a, self.b):
                xp = 10 if self.store.bump(g, user.id, "trade_xp", limit=XP_TRADES_PER_DAY) else 0
                # only a trade that completes the set pays (a set completed before is not paid twice)
                bonus = collection_bonus(self.store, g, user.id) if owned_before[user.id] < len(CARDS) else 0
                r = grant(self.store, g, user.id, bonus, xp, "echange", stats={"trades": 1})
                if bonus:
                    lines.append(f"{E.crown} {user.mention} **COLLECTION COMPLÈTE !** Bonus de "
                                 f"**{config.fmt(bonus)}** {E.candy} !")
                if r.line():
                    lines.append(f"{user.mention} {r.line()}")
            self.note = "\n".join(lines)
            self.state = "done"
            self.stop()
            await interaction.response.defer()
            data = await asyncio.to_thread(art.trade_gif, self.a.display_name, self.b.display_name, self.give,
                                           self.take, self.candies, random.randrange(1000))
            await self.update(interaction, attachments=[image_file(data, GIF_NAME)])

    async def on_timeout(self):
        if self.state in ("draft", "offer"):
            self.state = "expired"
            await self.update()


class Trade(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="echange", description="🃏 Échange des cartes maudites (et des bonbons) avec un membre")
    @app_commands.describe(membre="Avec qui veux-tu échanger ?", bonbons="Bonbons que tu ajoutes à ton offre (facultatif)")
    @app_commands.guild_only()
    async def echange(self, interaction: discord.Interaction, membre: discord.Member,
                      bonbons: app_commands.Range[int, 0, 100000] = 0):
        if membre.bot or membre.id == interaction.user.id:
            return await notice(interaction, "Choisis un vrai membre (pas toi-même, ni un bot) !")
        if bonbons and self.bot.store.candies(interaction.guild_id, interaction.user.id) < bonbons:
            return await notice(interaction, f"Tu n'as pas **{config.fmt(bonbons)}** bonbons à ajouter.")
        view = TradeView(self.bot, interaction.guild_id, interaction.user, membre, bonbons)
        await interaction.response.send_message(view=view, files=[await view.picture()], allowed_mentions=NO_PINGS)
        view.message = stable_message(await interaction.original_response())


async def setup(bot):
    await bot.add_cog(Trade(bot))
