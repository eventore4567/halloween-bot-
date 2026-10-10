"""Automatic CRYPT CUP: 10/30 minute signups, role pings and real match timers.

All important transitions are serialized and persisted. Discord Components V2
panels are restored after a restart. Role mention is sent only on signups, once.
"""
from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord.ext import commands, tasks

from .visuals import (
    RoundSignupLayout, RoundActiveLayout, RoundEndedLayout,
    VIOLET, text, divider, header, container,
)

LOG = logging.getLogger(__name__)


def closed_board():
    return discord.ui.LayoutView(timeout=None)


class RoundClosedLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(container(
            header("CRYPT CUP • REGISTRE", "LE PORTAIL EST SCELLÉ"),
            divider(),
            text("🔒 **Les inscriptions sont terminées.**\n"
                 "Les joueurs enregistrés ont reçu une invitation pour "
                 "rejoindre le défi dans le message suivant."),
            accent=VIOLET,
        ))


class Rounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._tick_lock = asyncio.Lock()

    def restore(self):
        restored = 0
        for row in self.bot.round_store.ongoing():
            if row["status"] == "signup" and row["signup_message_id"]:
                self.bot.add_view(
                    RoundSignupLayout(
                        self.bot, row,
                        self.bot.round_store.count(row["id"])
                    ),
                    message_id=row["signup_message_id"],
                )
                restored += 1
            elif row["status"] == "active" and row["challenge_message_id"]:
                self.bot.add_view(
                    RoundActiveLayout(
                        self.bot, row,
                        self.bot.round_store.count(row["id"]),
                    ),
                    message_id=row["challenge_message_id"],
                )
                restored += 1
        LOG.info("Restored %s CRYPT CUP persistent layouts", restored)

    async def cog_load(self):
        self.round_loop.start()

    def cog_unload(self):
        self.round_loop.cancel()

    def _channel(self, row):
        guild = self.bot.get_guild(row["guild_id"])
        return (
            guild,
            guild.get_channel(row["channel_id"]) if guild else None,
        )

    async def _post_signup(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel, discord.TextChannel):
            LOG.warning("Round %s cancelled: channel unavailable", row["id"])
            self.bot.round_store.cancel(row["id"])
            return
        role = guild.get_role(row["role_id"])
        if not role:
            self.bot.round_store.cancel(row["id"])
            LOG.warning("Round %s cancelled: role unavailable", row["id"])
            return
        bot_member = guild.me
        perms = channel.permissions_for(bot_member) if bot_member else None
        if not perms or not (perms.view_channel and
                            perms.send_messages and
                            perms.read_message_history):
            self.bot.round_store.cancel(row["id"])
            return
        if not role.mentionable and not perms.mention_everyone:
            self.bot.round_store.cancel(row["id"])
            LOG.warning("Role is not mentionable: %s", role.id)
            return
        try:
            message = await channel.send(
                content=role.mention,
                view=RoundSignupLayout(
                    self.bot,row,self.bot.round_store.count(row["id"])
                ),
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=[role]
                ),
            )
        except discord.HTTPException:
            LOG.exception("Could not send CRYPT CUP signup")
            self.bot.round_store.cancel(row["id"])
            return
        self.bot.round_store.bind(row["id"],"signup",message.id)

    async def _post_active(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel, discord.TextChannel):
            self.bot.round_store.cancel(row["id"])
            return
        if row["signup_message_id"]:
            try:
                previous = await channel.fetch_message(row["signup_message_id"])
                await previous.edit(
                    content=None,
                    view=RoundClosedLayout(),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.NotFound,discord.HTTPException):
                LOG.warning("Could not close signup panel for round %s", row["id"])
        try:
            message = await channel.send(
                view=RoundActiveLayout(
                    self.bot,row,self.bot.round_store.count(row["id"])
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            LOG.exception("Could not send CRYPT CUP active match")
            self.bot.round_store.cancel(row["id"])
            return
        self.bot.round_store.bind(row["id"],"active",message.id)

    async def _post_finished(self, row):
        guild, channel = self._channel(row)
        if not guild or not isinstance(channel, discord.TextChannel):
            return
        results = self.bot.round_store.round_standings(row["id"])
        outcome = RoundEndedLayout(row,results)
        if row["challenge_message_id"]:
            try:
                previous = await channel.fetch_message(
                    row["challenge_message_id"]
                )
                await previous.edit(
                    view=outcome,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            except (discord.HTTPException,discord.NotFound):
                LOG.warning("Couldn't edit end-of-round message %s", row["id"])
        try:
            await channel.send(
                view=outcome,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            LOG.exception("Could not send end-of-round results")

    @tasks.loop(seconds=20)
    async def round_loop(self):
        async with self._tick_lock:
            await self.tick()

    async def tick(self):
        # End phases before starting any new rounds.
        for rid in self.bot.round_store.finish_due():
            await self._post_finished(self.bot.round_store.round(rid))
        for rid in self.bot.round_store.activate_due():
            await self._post_active(self.bot.round_store.round(rid))

        # Repair interrupted posts after restart.
        for row in self.bot.round_store.ongoing():
            if row["status"] == "signup" and not row["signup_message_id"]:
                await self._post_signup(row)
            elif row["status"] == "active" and not row["challenge_message_id"]:
                await self._post_active(row)

        # Once the calendar season ends, never silently renew a paid prize.
        for cfg in self.bot.round_store.all_enabled():
            season = self.bot.competition.season(cfg["guild_id"])
            if not season or season["status"] != "active":
                self.bot.round_store.suspend(cfg["guild_id"])

        for rid in self.bot.round_store.claim_due():
            row = self.bot.round_store.round(rid)
            season = self.bot.competition.season(row["guild_id"])
            if not season or season["status"] != "active":
                self.bot.round_store.cancel(rid)
                continue
            await self._post_signup(row)

    @round_loop.before_loop
    async def before_rounds(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Rounds(bot))
