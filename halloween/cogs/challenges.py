"""/defis — 3 daily challenges, 2 weekly challenges, rewards to collect."""
from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from .. import challenges as Q
from .. import config
from ..art.challenges import board_png
from ..emojis import E
from ..ui import GameView, Panel, button, image_file, nav, relative

PNG_NAME = "defis.png"
GAME_LABELS = {"quiz": "Grand Frisson", "house": "Maison", "race": "Course", "ritual": "Rituel", "reflex": "Réflexe",
               "ouija": "Ouija", "shell": "Bonneteau", "memory": "Mémoire", "hangman": "Pendu", "hunt": "Chasse",
               "cauldron": "Formule", "slots": "Machine", "motus": "Motus", "hilo": "Plus ou Moins", "hub": "Tous les jeux"}


class ChallengesView(GameView):
    kicker = "DÉFIS"
    owner_hint = "Ouvre tes propres défis avec /defis."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.flash = ""

    def _rows(self, quests, period):
        g, u = self.guild_id, self.owner_id
        return [dict(q=q, text=q.text, icon=q.icon, goal=q.goal, reward=q.reward,
                     progress=Q.progress(self.store, g, u, q, period), claimed=Q.claimed(self.store, g, u, q, period))
                for q in quests]

    def rows(self):
        g, u = self.guild_id, self.owner_id
        day, week = config.today(), Q.week_key()
        return self._rows(Q.daily_quests(g, u, day), day), self._rows(Q.weekly_quests(g, u, week), week)

    def picture(self) -> bytes:
        daily, weekly = self.rows()
        bonus = self.store.counter(self.guild_id, self.owner_id, "qc:all") > 0
        return board_png(daily, weekly, bonus, Q.ALL_DONE_BONUS)

    async def extra_files(self):
        return [image_file(await asyncio.to_thread(self.picture), PNG_NAME)]

    def build(self) -> Panel:
        p = Panel("pink")
        daily, weekly = self.rows()
        ready = [r for r in daily + weekly if r["progress"] >= r["goal"] and not r["claimed"]]
        left = sum(1 for r in daily if r["claimed"])
        body = (f"{E.hourglass} Nouveaux défis du jour {relative(config.next_midnight_ts())} · "
                f"de la semaine {relative(Q.next_monday_ts())}\n"
                f"{E.gift} Termine les 3 défis du jour : **+{Q.ALL_DONE_BONUS}** {E.candy} et **1 ticket de roue** "
                f"({left}/3 récupérés)")
        if self.flash:
            body = self.flash + "\n" + body
        p.title("Tes défis", icon="scroll", body=body)
        p.image(PNG_NAME)
        total = sum(r["reward"] for r in ready)
        p.row(button(f"Récupérer {config.fmt(total)} bonbons" if ready else "Rien à récupérer pour l'instant",
                     "candy_bag", "success" if ready else "secondary", self._claim, disabled=not ready))
        games = []
        for r in daily + weekly:
            key = r["q"].game
            if key and r["progress"] < r["goal"] and key not in games and key in self.bot.openers:
                games.append(key)
        if games:
            p.row(*[nav(k, self.owner_id, GAME_LABELS.get(k, k)[:30], "lightning", "primary") for k in games[:4]],
                  nav("hub", self.owner_id, "Menu", "pumpkin") if "hub" not in games[:4] else None)
        else:
            p.row(nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _claim(self, interaction):
        async with self.lock:
            total, paid, bonus = Q.claim_all(self.store, self.guild_id, self.owner_id)
            if paid or bonus:
                names = ", ".join(f"*{q.text}*" for q in paid)
                self.flash = f"{E.sparkle} **+{config.fmt(total)}** {E.candy} récupérés ! {names}"
                if bonus:
                    self.flash += f"\n{E.trophy} **Les 3 défis du jour sont faits !** Bonus et ticket de roue ajoutés."
            await interaction.response.defer()
            data = await asyncio.to_thread(self.picture)
            await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["defis"] = self.open

    async def open(self, interaction, edit=False):
        await ChallengesView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="defis", description="🎯 Tes défis du jour et de la semaine")
    @app_commands.guild_only()
    async def defis(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Challenges(bot))
