"""Automatic Halloween Cup registration and match announcements.

One-time /setup selects text channel, mention role, recurrence (30/60/120m),
and registration (10/30m). Announcements mention ONLY the configured role,
once when registration opens. A round then transitions to a 10-minute live
challenge, announces results and schedules the next round.
"""
from __future__ import annotations

import asyncio
import logging
import time
import discord
from discord.ext import commands, tasks

from .common import card, fail, themed_view
from .round_store import PLAY_MINUTES

LOG = logging.getLogger(__name__)


def signup_card(round_row, total):
    return card(
        "Les portes du cimetière s'ouvrent",
        "🦇 **NOUVELLE MANCHE • HALLOWEEN CUP**\n"
        "Le portail de l'arène est ouvert. Rejoins les autres chasseurs !",
        theme="pumpkin",
        sections=[
            ("🎟️  INSCRIPTIONS", f"**{total} participants**", True),
            ("⏳  FERMETURE", f"<t:{round_row['signup_ends_at']}:R>", True),
            ("🏆  APRÈS LA FERMETURE",
             f"Un défi de réflexion de **{PLAY_MINUTES} minutes** "
             "commencera automatiquement.", False),
            ("🕯️  PARTICIPATION",
             "Gratuite, une inscription par personne. "
             "Les bonbons et objets ne déterminent pas le classement officiel.",
             False),
        ],
        note="Clique sur Participer avant la fin du compte à rebours.",
        thumbnail=True,
    )


def active_card(round_row, total):
    return card(
        "La manche a commencé",
        "💀 **Les portes sont fermées : les défis commencent !**",
        theme="danger",
        sections=[
            ("🏆  CHASSEURS INSCRITS", f"**{total}**", True),
            ("⏳  FIN DE LA MANCHE", f"<t:{round_row['ends_at']}:R>", True),
            ("🧩  TON OBJECTIF",
             "Réponds à **une épreuve individuelle**. "
             "Les bonnes réponses ajoutent des points à ton classement "
             "de saison et au score de cette manche.", False),
            ("🔒  INTÉGRITÉ",
             "Seules les personnes inscrites pendant la fenêtre de participation "
             "peuvent jouer. Un défi par manche et trois maximum par jour UTC.",
             False),
        ],
        note="Clique sur Jouer mon défi. Les résultats seront annoncés automatiquement.",
        thumbnail=True,
    )


def finished_card(round_row, standings):
    med = ["🥇","🥈","🥉","🎃","🦇"]
    rows = [
        f"{med[i]} <@{r['user_id']}> — **{r['score']} points**"
        for i,r in enumerate(standings[:5])
    ]
    return card(
        "La manche est terminée",
        "🌙 Le cimetière retrouve son calme. Le classement de saison "
        "reste ouvert jusqu'à la fin de la compétition.",
        theme="gold",
        sections=[
            ("🏆  TOP DE LA MANCHE",
             "\n".join(rows) if rows else
             "🕸️ Aucun compétiteur n'a joué cette manche.", False),
            ("🍬  LES BONBONS", "La boutique et les jeux restent accessibles.", False),
        ],
        note="Les égalités de points nécessitent un départage équitable "
             "avant toute attribution de récompense réelle.",
    )


class RoundJoinView(discord.ui.View):
    def __init__(self, bot, round_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.round_id = round_id
        button = discord.ui.Button(
            label="Participer à la manche",
            emoji="🎟️",
            style=discord.ButtonStyle.success,
            custom_id=f"halloween:round:join:{round_id}",
        )
        button.callback = self.join
        self.add_item(button)
        themed_view(self)

    async def join(self, interaction):
        if not interaction.guild or interaction.user.bot:
            return await fail(interaction, "Réservé aux membres de ce serveur.")
        result = self.bot.round_store.join(
            self.round_id, interaction.guild.id, interaction.user.id
        )
        if result == "closed":
            return await fail(interaction, "Les inscriptions sont terminées.")
        if result == "already_joined":
            return await fail(interaction, "Tu es déjà inscrit à cette manche.")
        self.bot.competition.join(interaction.guild.id, interaction.user.id)
        row = self.bot.round_store.round(self.round_id)
        count = self.bot.round_store.count(self.round_id)
        if row and row["status"] == "signup":
            try:
                await interaction.response.edit_message(
                    embed=signup_card(row, count),
                    view=self,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "✅ Inscription enregistrée !", ephemeral=True
                    )


class RoundPlayView(discord.ui.View):
    def __init__(self, bot, round_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.round_id = round_id
        button = discord.ui.Button(
            label="Jouer mon défi",
            emoji="🧩",
            style=discord.ButtonStyle.primary,
            custom_id=f"halloween:round:play:{round_id}",
        )
        button.callback = self.play
        self.add_item(button)
        themed_view(self)

    async def play(self, interaction):
        if not interaction.guild:
            return await fail(interaction, "Cette manche appartient à un serveur.")
        status, row = self.bot.round_store.check(
            interaction.guild.id, interaction.user.id
        )
        if not row or row["id"] != self.round_id:
            return await fail(interaction, "Cette manche est terminée.")
        if status != "ready":
            message = {
                "signup": "Attends la fermeture des inscriptions.",
                "not_joined": "Tu ne t'es pas inscrit pendant la période prévue.",
                "expired": "Cette manche est terminée.",
            }.get(status, "Manche indisponible.")
            return await fail(interaction, message)
        remaining = self.bot.competition.remaining_modes(
            interaction.guild.id, interaction.user.id
        )
        if not remaining:
            return await fail(interaction, "Tu as déjà utilisé tes trois défis "
                              "du jour. Reviens demain à 00:00 UTC.")
        from .competition import ChallengeView
        from .competition_store import MODES
        await interaction.response.send_message(
            embed=card(
                "Choisis ton épreuve",
                "🗝️ **Une seule épreuve peut être lancée par manche.**",
                theme="night",
                sections=[
                    ("🧩  ENCORE DISPONIBLES",
                     "\n".join(
                         f"✅ {MODES[mode]['title']} • "
                         f"**{MODES[mode]['points']} points**"
                         for mode in remaining
                     ), False),
                    ("⏳  FIN", f"<t:{row['ends_at']}:R>", False),
                ],
                note="Lancer une épreuve consomme la tentative, même "
                     "si tu quittes le panneau.",
            ),
            view=ChallengeView(
                self.bot, interaction.guild.id, interaction.user.id
            ),
            ephemeral=True,
        )


class Rounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._tick_lock = asyncio.Lock()

    def restore(self):
        total = 0
        for row in self.bot.round_store.ongoing():
            if row["status"] == "signup" and row["signup_message_id"]:
                self.bot.add_view(
                    RoundJoinView(self.bot, row["id"]),
                    message_id=row["signup_message_id"]
                )
                total += 1
            elif row["status"] == "active" and row["challenge_message_id"]:
                self.bot.add_view(
                    RoundPlayView(self.bot, row["id"]),
                    message_id=row["challenge_message_id"]
                )
                total += 1
        LOG.info("Restored %s Halloween Cup round views", total)

    async def cog_load(self):
        self.round_loop.start()

    def cog_unload(self):
        self.round_loop.cancel()

    def _channel(self, row):
        guild = self.bot.get_guild(row["guild_id"])
        if not guild:
            return None, None
        return guild, guild.get_channel(row["channel_id"])

    async def _post_signup(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel, discord.TextChannel):
            LOG.warning("Missing Halloween Cup signup channel: guild=%s",
                        row["guild_id"])
            self.bot.round_store.cancel(row["id"])
            return
        role = guild.get_role(row["role_id"])
        if not role:
            self.bot.round_store.cancel(row["id"])
            LOG.warning("Role no longer exists in guild=%s", guild.id)
            return
        member = guild.me
        perms = channel.permissions_for(member) if member else None
        if not perms or not (perms.view_channel and perms.send_messages
                            and perms.embed_links):
            self.bot.round_store.cancel(row["id"])
            LOG.warning("Missing send permissions for guild=%s", guild.id)
            return
        # Role must be mentionable or the bot must possess mention_everyone.
        # Never fall back to @everyone or @here.
        if not role.mentionable and not perms.mention_everyone:
            self.bot.round_store.cancel(row["id"])
            LOG.warning("Role %s not mentionable for Halloween Cup", role.id)
            return
        try:
            message = await channel.send(
                content=role.mention,
                embed=signup_card(row, self.bot.round_store.count(row["id"])),
                view=RoundJoinView(self.bot, row["id"]),
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=[role]
                ),
            )
        except discord.HTTPException:
            LOG.exception("Could not publish Halloween Cup signup")
            self.bot.round_store.cancel(row["id"])
            return
        self.bot.round_store.bind(row["id"], "signup", message.id)

    async def _post_active(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel,discord.TextChannel):
            self.bot.round_store.cancel(row["id"])
            return
        if row["signup_message_id"]:
            try:
                previous = await channel.fetch_message(row["signup_message_id"])
                await previous.edit(
                    embed=card(
                        "Inscriptions terminées",
                        "🔒 La manche a commencé. "
                        "Clique sur le nouveau panneau pour jouer.",
                        theme="night",
                    ),
                    view=None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.NotFound,discord.HTTPException):
                pass
        try:
            message = await channel.send(
                embed=active_card(row,self.bot.round_store.count(row["id"])),
                view=RoundPlayView(self.bot,row["id"]),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            LOG.exception("Could not publish active Halloween Cup round")
            self.bot.round_store.cancel(row["id"])
            return
        self.bot.round_store.bind(row["id"],"active",message.id)

    async def _post_finished(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel,discord.TextChannel):
            return
        standings = self.bot.round_store.round_standings(row["id"])
        if row["challenge_message_id"]:
            try:
                message=await channel.fetch_message(row["challenge_message_id"])
                await message.edit(
                    embed=finished_card(row,standings),
                    view=None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            except (discord.NotFound,discord.HTTPException):
                pass
        try:
            await channel.send(
                embed=finished_card(row,standings),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            LOG.exception("Could not publish Halloween Cup results")

    @tasks.loop(seconds=20)
    async def round_loop(self):
        async with self._tick_lock:
            await self.tick()

    async def tick(self):
        # Complete phases first, to avoid opening overlapping rounds.
        for rid in self.bot.round_store.finish_due():
            row = self.bot.round_store.round(rid)
            await self._post_finished(row)
        for rid in self.bot.round_store.activate_due():
            row = self.bot.round_store.round(rid)
            await self._post_active(row)

        # If restarted while processing a state transition, repair the post.
        for row in self.bot.round_store.ongoing():
            if row["status"]=="signup" and not row["signup_message_id"]:
                await self._post_signup(row)
            elif row["status"]=="active" and not row["challenge_message_id"]:
                await self._post_active(row)

        # Only run matches while an official season is open.
        for config in self.bot.round_store.all_enabled():
            season = self.bot.competition.season(config["guild_id"])
            if season and season["status"]!="active":
                self.bot.round_store.suspend(config["guild_id"])
        for rid in self.bot.round_store.claim_due():
            row = self.bot.round_store.round(rid)
            season = self.bot.competition.season(row["guild_id"])
            if not season or season["status"]!="active":
                self.bot.round_store.cancel(rid)
                continue
            await self._post_signup(row)

    @round_loop.before_loop
    async def before_rounds(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Rounds(bot))
