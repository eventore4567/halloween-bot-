"""Daily reminder (opt-in): every evening, ping the players who asked for it and still have
their October calendar box (or their daily chest) waiting."""
from __future__ import annotations

import datetime as dt
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..emojis import E
from ..ui import Panel, banner_file, nav, notice
from .seasonal import october_day

LOG = logging.getLogger(__name__)
DEFAULT_HOUR = 18
MAX_MENTIONS = 40  # per message


def _key(g):
    return f"remind:{g}"


def subscribers(store, g) -> list[int]:
    return list(store.meta_get(_key(g), []))


def is_subscribed(store, g, u) -> bool:
    return u in subscribers(store, g)


def toggle(store, g, u) -> bool:
    """Switch the reminder of a member; returns the new state."""
    subs = subscribers(store, g)
    if u in subs:
        subs.remove(u)
        on = False
    else:
        subs.append(u)
        on = True
    store.meta_set(_key(g), subs)
    return on


def reminder_hour(store, g) -> int:
    return int(store.meta_get(f"remind_hour:{g}", DEFAULT_HOUR))


def pending(store, g, now: dt.datetime) -> list[tuple[int, list[str]]]:
    """Subscribers with something left to open today, and what."""
    year, day = october_day(now)
    today = config.today(now)
    out = []
    for u in subscribers(store, g):
        todo = []
        if day is not None and f"cal:{year}-{day:02d}" not in store.owned(g, u):
            todo.append("calendar")
        if store.player(g, u)["last_daily"] != today:
            todo.append("daily")
        if todo:
            out.append((u, todo))
    return out


def reminder_view(day: int | None, todo: tuple[str, ...], mentions: list[int],
                  server: str | None = None) -> discord.ui.LayoutView:
    """The reminder panel for members who still have ``todo`` (calendar and/or daily) to open.

    ``server`` is set for a private message: no buttons there, the games live in the server.
    """
    view = discord.ui.LayoutView(timeout=None)
    p = Panel("orange").banner("daily")
    calendar, daily = "calendar" in todo and day is not None, "daily" in todo
    if calendar:
        title = "C'EST HALLOWEEN ! Ta dernière case t'attend" if day == 31 else f"La case du {day} octobre t'attend !"
        what = "ta case du **calendrier d'octobre**" + (" et ton **coffre du jour**" if daily else "")
        body = f"{E.gift} Ouvre {what} avant minuit."
        left = 31 - day
        if left:
            body += f"\n{E.pumpkin_lit} Plus que **{left}** nuit{'s' if left > 1 else ''} avant Halloween…"
    else:
        title = "Ton coffre du jour t'attend !"
        body = f"{E.chest} N'oublie pas ton **coffre du jour** avant minuit : ta série de jours en dépend !"
    p.title(title, icon="gift", body=body)
    if mentions:
        p.text(" ".join(f"<@{u}>" for u in mentions))
    if server:
        cmds = " et ".join(c for c, on in (("`/calendrier`", calendar), ("`/quotidien`", daily)) if on)
        p.text(f"{E.lightning} Rendez-vous sur **{server}** : {cmds}.")
    p.text(f"-# {E.lock} Tu reçois ce rappel parce que tu l'as activé. `/rappel` pour l'arrêter.")
    if not server:  # anyone clicking opens their own panel
        buttons = []
        if calendar:
            buttons.append(nav("calendar", 0, "Ouvrir ma case", "gift", "primary"))
        if daily:
            buttons.append(nav("daily", 0, "Coffre du jour", "chest", "success"))
        p.row(*buttons)
    view.add_item(p.container())
    return view


class _NoChannel(Exception):
    """No events channel is configured (or it disappeared)."""


def tz_name() -> str:
    return getattr(config.TZ, "key", None) or str(config.TZ)


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.tick.is_running():
            self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()

    @tasks.loop(minutes=1)
    async def tick(self):
        now = dt.datetime.now(config.TZ)
        for guild in list(self.bot.guilds):
            try:
                await self.maybe_remind(guild.id, now)
            except Exception:  # noqa: BLE001 - one guild must not stop the others
                LOG.exception("reminder failed for guild %s", guild.id)

    async def _members(self, g: int, users: list[int]) -> list[int]:
        """Keep the members still in the guild; unsubscribe the ones who left."""
        guild = self.bot.get_guild(g)
        if guild is None:
            return []
        kept = []
        for u in users:
            if guild.get_member(u) is None:
                try:
                    await guild.fetch_member(u)
                except discord.NotFound:
                    toggle(self.bot.store, g, u)  # left the server: stop reminding them
                    continue
                except discord.HTTPException:
                    pass  # unknown for now: still remind them
            kept.append(u)
        return kept

    async def maybe_remind(self, g: int, now: dt.datetime) -> int:
        """Send today's reminder once, at or after the guild's hour. Returns how many members were reminded.

        The day is only marked as done once the messages went out, so a failure is retried a minute later.
        """
        store = self.bot.store
        today = config.today(now)
        if now.hour < reminder_hour(store, g) or store.meta_get(f"remind_sent:{g}") == today:
            return 0
        _year, day = october_day(now)
        groups: dict[tuple[str, ...], list[int]] = {}
        for u, todo in pending(store, g, now):
            groups.setdefault(tuple(todo), []).append(u)
        for todo in list(groups):
            groups[todo] = await self._members(g, groups[todo])
        total = sum(len(v) for v in groups.values())
        reached = 0
        if total:
            channel = self.bot.get_channel(store.guild(g)["drop_channel"] or 0)
            try:
                if channel is None:
                    raise _NoChannel
                for todo, users in groups.items():
                    for i in range(0, len(users), MAX_MENTIONS):
                        chunk = users[i:i + MAX_MENTIONS]
                        await channel.send(view=reminder_view(day, todo, chunk), files=[await banner_file("daily")],
                                           allowed_mentions=discord.AllowedMentions(
                                               users=[discord.Object(u) for u in chunk]))
                reached = total
            except (_NoChannel, discord.Forbidden, discord.HTTPException):
                reached = await self._private(g, day, groups)  # channel missing or unusable: private messages
        store.meta_set(f"remind_sent:{g}", today)
        return reached

    async def _private(self, g: int, day, groups) -> int:
        guild = self.bot.get_guild(g)
        name = guild.name if guild else "ton serveur"
        sent = 0
        for todo, users in groups.items():
            for u in users:
                try:
                    user = self.bot.get_user(u) or await self.bot.fetch_user(u)
                    await user.send(view=reminder_view(day, todo, [], name), files=[await banner_file("daily")])
                    sent += 1
                except (discord.Forbidden, discord.HTTPException):
                    continue
        return sent

    @app_commands.command(name="rappel", description="🔔 Active ou coupe ton rappel quotidien (calendrier et coffre du jour)")
    @app_commands.guild_only()
    async def rappel(self, interaction: discord.Interaction):
        store = self.bot.store
        on = toggle(store, interaction.guild_id, interaction.user.id)
        hour = reminder_hour(store, interaction.guild_id)
        if on:
            await notice(interaction, f"{E.check} **Rappel activé !** Chaque jour vers **{hour} h** ({tz_name()}), je te préviens si ta "
                                      f"case du calendrier ou ton coffre du jour t'attendent encore.\n"
                                      f"-# Refais `/rappel` pour l'arrêter.", icon="gift", color="green")
        else:
            await notice(interaction, "Rappel désactivé. Refais `/rappel` pour le remettre.", icon="lock", color="purple")


async def setup(bot):
    await bot.add_cog(Reminder(bot))
