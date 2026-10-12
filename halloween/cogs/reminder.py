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


def reminder_view(day: int | None, mentions: list[int], server: str | None = None) -> discord.ui.LayoutView:
    """The reminder panel; ``server`` is set for a private message (no buttons: games live in the server)."""
    view = discord.ui.LayoutView(timeout=None)
    p = Panel("orange").banner("daily")
    if day is not None:
        left = 31 - day
        title = "C'EST HALLOWEEN ! Ta dernière case t'attend" if day == 31 else f"La case du {day} octobre t'attend !"
        body = (f"{E.gift} Ouvre ta case du **calendrier d'octobre** et ton **coffre du jour** avant minuit."
                + (f"\n{E.pumpkin_lit} Plus que **{left}** nuit{'s' if left > 1 else ''} avant Halloween…" if left else ""))
    else:
        title = "Ton coffre du jour t'attend !"
        body = f"{E.chest} N'oublie pas ton **coffre du jour** : ta série de jours en dépend !"
    p.title(title, icon="gift", body=body)
    if mentions:
        p.text(" ".join(f"<@{u}>" for u in mentions))
    if server:
        p.text(f"{E.lightning} Rendez-vous sur **{server}** : `/calendrier` et `/quotidien`.")
    p.text(f"-# {E.lock} Tu reçois ce rappel parce que tu l'as activé. `/rappel` pour l'arrêter.")
    if not server:  # anyone clicking opens their own panel
        buttons = [nav("daily", 0, "Coffre du jour", "chest", "success")]
        if day is not None:
            buttons.insert(0, nav("calendar", 0, "Ouvrir ma case", "gift", "primary"))
        p.row(*buttons)
    view.add_item(p.container())
    return view


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

    async def maybe_remind(self, g: int, now: dt.datetime) -> int:
        """Send today's reminder once, at or after the guild's hour. Returns how many members were reminded."""
        store = self.bot.store
        today = config.today(now)
        if now.hour < reminder_hour(store, g) or store.meta_get(f"remind_sent:{g}") == today:
            return 0
        store.meta_set(f"remind_sent:{g}", today)
        todo = pending(store, g, now)
        if not todo:
            return 0
        _year, day = october_day(now)
        users = [u for u, _what in todo]
        channel = self.bot.get_channel(store.guild(g)["drop_channel"] or 0)
        if channel is not None:
            for i in range(0, len(users), MAX_MENTIONS):
                chunk = users[i:i + MAX_MENTIONS]
                await channel.send(view=reminder_view(day, chunk), files=[await banner_file("daily")],
                                   allowed_mentions=discord.AllowedMentions(users=[discord.Object(u) for u in chunk]))
            return len(users)
        sent = 0
        guild = self.bot.get_guild(g)
        name = guild.name if guild else "ton serveur"
        for u in users:  # no events channel: private messages
            try:
                user = self.bot.get_user(u) or await self.bot.fetch_user(u)
                await user.send(view=reminder_view(day, [], name), files=[await banner_file("daily")])
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
            await notice(interaction, f"{E.check} **Rappel activé !** Chaque jour vers **{hour} h**, je te préviens si ta "
                                      f"case du calendrier ou ton coffre du jour t'attendent encore.\n"
                                      f"-# Refais `/rappel` pour l'arrêter.", icon="gift", color="green")
        else:
            await notice(interaction, "Rappel désactivé. Refais `/rappel` pour le remettre.", icon="lock", color="purple")


async def setup(bot):
    await bot.add_cog(Reminder(bot))
