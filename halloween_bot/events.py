"""Persistent automatic events: one claimant, one reward, surviving bot restarts."""
from __future__ import annotations
import logging
import random

import discord
from discord.ext import commands,tasks

from .common import card, fail, themed_view
from .content import EVENTS

LOG=logging.getLogger(__name__)


class EventClaim(discord.ui.View):
    def __init__(self,bot,event_id):
        super().__init__(timeout=None)
        self.bot=bot
        self.event_id=event_id
        button=discord.ui.Button(
            label="Attraper les bonbons",emoji="🍬",
            style=discord.ButtonStyle.success,
            custom_id=f"halloween:event:{event_id}")
        button.callback=self.claim
        self.add_item(button)
        themed_view(self)

    async def claim(self,interaction:discord.Interaction):
        if not interaction.guild or interaction.user.bot:
            return await fail(interaction,"Cet événement est réservé aux joueurs.")
        reward=self.bot.store.claim(self.event_id,interaction.guild.id,interaction.user.id)
        if not reward:
            return await fail(interaction,"Trop tard ! Cet événement est terminé.")
        for button in self.children:
            button.disabled=True
        await interaction.response.edit_message(
            embed=card("Apparition capturée",
                       f"🏆 **{interaction.user.mention} remporte cette apparition !**",
                       theme="success",
                       sections=[("🍬  BUTIN", f"**+{reward} bonbons**", False)],
                       note="Une autre créature apparaîtra prochainement."),
            view=self,allowed_mentions=discord.AllowedMentions.none())
        self.stop()


class Events(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    def restore(self):
        n=0
        for row in self.bot.store.pending_events():
            self.bot.add_view(EventClaim(self.bot,row["id"]),message_id=row["message_id"])
            n+=1
        LOG.info("Restored %s Halloween event buttons",n)

    async def cog_load(self):
        self.event_loop.start()
        self.cleanup_loop.start()

    def cog_unload(self):
        self.event_loop.cancel()
        self.cleanup_loop.cancel()

    @tasks.loop(minutes=20)
    async def event_loop(self):
        for config in self.bot.store.channels():
            guild=self.bot.get_guild(config["guild_id"])
            if not guild:
                continue
            channel=guild.get_channel(config["event_channel"])
            if not isinstance(channel,discord.TextChannel):
                continue
            title,description=random.choice(EVENTS)
            amount=random.randint(90,275)
            event_id=self.bot.store.spawn(guild.id,channel.id,title,amount)
            if event_id is None:
                continue
            try:
                message=await channel.send(
                    embed=card(title, description,
                               theme="gold" if "BONBONS" in title else "night",
                               sections=[
                                   ("🍬  RÉCOMPENSE", f"**{amount} bonbons**", True),
                                   ("⏳  DURÉE", "**3 minutes**", True),
                                   ("🦇  COMMENT PARTICIPER",
                                    "Le premier joueur à utiliser le bouton "
                                    "récupère toute la récompense.", False),
                               ]),
                    view=EventClaim(self.bot,event_id),
                    allowed_mentions=discord.AllowedMentions.none())
                self.bot.store.event_message(event_id,message.id)
            except (discord.Forbidden,discord.HTTPException):
                LOG.exception("Failed to send Halloween event to guild %s",guild.id)
                self.bot.store.close_event(event_id)

    @event_loop.before_loop
    async def before_events(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=45)
    async def cleanup_loop(self):
        for row in self.bot.store.expired_events():
            guild=self.bot.get_guild(row["guild_id"])
            if not guild or not row["message_id"]:
                continue
            channel=guild.get_channel(row["channel_id"])
            if not isinstance(channel,discord.TextChannel):
                continue
            try:
                message=await channel.fetch_message(row["message_id"])
                await message.edit(
                    embed=card("Apparition disparue",
                               "🌫️ La créature s'est évanouie dans le brouillard.",
                               theme="night",
                               sections=[("🕯️  TROP TARD",
                                          "Personne n'a attrapé le butin à temps.", False)]),
                    view=None)
            except (discord.Forbidden,discord.NotFound,discord.HTTPException):
                pass

    @cleanup_loop.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Events(bot))
