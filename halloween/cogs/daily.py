"""/quotidien — daily chest with a 7-day streak."""
from __future__ import annotations

import asyncio
import datetime as dt
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, nav, relative


def daily_amount(streak: int, rnd=random) -> int:
    step = min(streak, config.DAILY_STREAK_MAX) - 1
    return config.DAILY_BASE + config.DAILY_STREAK_STEP * step + rnd.randint(0, 50)


class DailyView(GameView):
    banner_key = "daily"
    kicker = "COFFRE DU JOUR"

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.state = "closed"
        self.result = None
        self.streak = 0

    def streak_row(self, streak):
        cells = []
        for i in range(1, config.DAILY_STREAK_MAX + 1):
            if i <= streak:
                cells.append(E.fire)
            elif i == config.DAILY_STREAK_MAX:
                cells.append(E.gift)
            else:
                cells.append(E.lock)
        return " ".join(cells)

    def build(self) -> Panel:
        p = Panel("gold").banner(self.banner_key)
        nxt = relative(config.next_midnight_ts())
        if self.state == "opening":
            p.title("Le coffre tremble…", icon="chest",
                    body=f"{E.sparkle} Les cadenas sautent un par un… {E.sparkle}")
        elif self.state == "opened":
            r = self.result
            body = (f"{E.candy_bag} Tu trouves **{config.fmt(r['reward'].candies)}** bonbons !\n{r['reward'].line()}")
            if r.get("booster"):
                body += f"\n{E.gift} **Série de 7 jours !** Un booster de cartes t'attend dans `/cartes`."
            p.title("Coffre ouvert !", icon="chest", body=body, thumb=E.url("candy_bag"))
            p.sep()
            p.text(f"### {E.fire} Série : {self.streak} jour{'s' if self.streak > 1 else ''}\n"
                   f"{self.streak_row(min(self.streak, config.DAILY_STREAK_MAX))}\n"
                   f"-# Reviens {nxt} pour garder ta série. Chaque jour de série = +{config.DAILY_STREAK_STEP} bonbons.")
        else:  # already claimed
            p.title("Déjà ouvert aujourd'hui", icon="lock",
                    body=f"Ton coffre se rechargera {nxt}.\nEn attendant, d'autres jeux t'attendent !")
            p.sep()
            p.text(f"### {E.fire} Série : {self.streak} jour{'s' if self.streak > 1 else ''}\n"
                   f"{self.streak_row(min(self.streak, config.DAILY_STREAK_MAX))}")
        p.sep()
        o = self.owner_id
        p.row(nav("wheel", o, "Roue du destin", "wheel", "primary"), nav("quiz", o, "Quiz", "crystal"),
              nav("hub", o, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def run(self, interaction, edit):
        g, u = self.guild_id, self.owner_id
        now = dt.datetime.now(config.TZ)
        day = config.today(now)
        yesterday = config.today(now - dt.timedelta(days=1))
        streak = self.store.claim_daily(g, u, day, yesterday)
        if streak is None:
            self.state = "claimed"
            self.streak = self.store.player(g, u)["streak"]
            return await self.start(interaction, edit)
        self.streak = streak
        amount = daily_amount(streak)
        reward = grant(self.store, g, u, amount, 25, "quotidien")
        booster = streak % config.DAILY_STREAK_MAX == 0
        if booster:
            self.store.give_item(g, u, "booster")
        self.result = dict(reward=reward, booster=booster)
        self.state = "opening"
        await self.start(interaction, edit)
        await asyncio.sleep(1.6)
        self.state = "opened"
        await self.push()


class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["daily"] = self.open

    async def open(self, interaction, edit=False):
        await DailyView(self.bot, interaction).run(interaction, edit)

    @app_commands.command(name="quotidien", description="🧰 Ouvre ton coffre du jour (série jusqu'à 7 jours)")
    @app_commands.guild_only()
    async def quotidien(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Daily(bot))
