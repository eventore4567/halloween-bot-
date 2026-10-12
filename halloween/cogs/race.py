"""/course — bet on one of four witches in an animated broom race."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import neon
from ..art.race import race_gif
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

RACERS = [
    dict(name="Morgane", color=neon.GREEN, emoji="witch", style="success", desc="Rapide au départ"),
    dict(name="Ombrelune", color=neon.PURPLE, emoji="moon", style="primary", desc="Vole la nuit sans bruit"),
    dict(name="Citrouillette", color=neon.ORANGE, emoji="pumpkin", style="secondary", desc="Imprévisible"),
    dict(name="Griffe", color=neon.RED, emoji="bat", style="danger", desc="Tout ou rien"),
]
PAYOUT = 3.6  # equal chances, slight house edge
BETS = [25, 100, 250, 500]
RACE_FILE = "course.gif"


class RaceView(GameView):
    banner_key = "race"
    owner_hint = "Lance ta propre course avec /course."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.bet = 100
        self.pick = None
        self.winner = None
        self.state = "bet" if allowed else "empty"
        self.reward = None

    def build(self) -> Panel:
        p = Panel("green")
        if self.state in ("racing", "done"):
            p.image(RACE_FILE)
        else:
            p.banner(self.banner_key)
        if self.state == "empty":
            p.title("Les balais sont au garage", icon="witch",
                    body=f"Plus de courses aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "racing":
            r = RACERS[self.pick]
            p.title("C'est parti !", icon="lightning",
                    body=f"Tu as misé **{config.fmt(self.bet)}** {E.candy} sur **{r['name']}** {E(r['emoji'])}…")
            p.footer(self.footer())
            return p
        if self.state == "done":
            r, w = RACERS[self.pick], RACERS[self.winner]
            if self.pick == self.winner:
                p.title(f"{w['name']} gagne !", icon="trophy",
                        body=f"Ta sorcière l'emporte ! {self.reward.line()}")
            else:
                p.title(f"{w['name']} gagne…", icon="skull",
                        body=f"{r['name']} arrive trop tard. Tu perds ta mise de **{config.fmt(self.bet)}** {E.candy}.\n"
                             f"{self.reward.line()}")
            p.sep()
            left = self.store.remaining(self.guild_id, self.owner_id, "race")
            p.row(nav("race", self.owner_id, f"Nouvelle course ({left})", "witch", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        lines = [f"`{i + 1}` {E(r['emoji'])} **{r['name']}** — *{r['desc']}*" for i, r in enumerate(RACERS)]
        p.title("Sur quelle sorcière paries-tu ?", icon="witch",
                body=f"Choisis ta mise puis ta sorcière. Si elle gagne, tu remportes **×{PAYOUT:g}** ta mise !\n"
                     + "\n".join(lines))
        p.sep()
        bal = self.store.candies(self.guild_id, self.owner_id)
        p.text(f"{E.candy_bag} Mise : **{config.fmt(self.bet)}** {E.candy} · gain possible "
               f"**{config.fmt(int(self.bet * PAYOUT))}** {E.candy}")
        p.row(*[button(f"{b}", "candy", "primary" if b == self.bet else "secondary", self._set_bet(b),
                       disabled=b > bal) for b in BETS])
        p.row(*[button(r["name"], r["emoji"], r["style"], self._go(i), disabled=bal < self.bet)
                for i, r in enumerate(RACERS)])
        p.footer(self.footer("Seul toi peux parier ici"))
        return p

    def _set_bet(self, amount):
        async def cb(interaction):
            self.bet = amount
            await self.refresh(interaction)
        return cb

    def _go(self, index):
        async def cb(interaction):
            async with self.lock:
                if self.state != "bet":
                    return await interaction.response.defer()
                g, u = self.guild_id, self.owner_id
                try:
                    self.store.spend(g, u, self.bet, "course")
                except NotEnough:
                    return await self.refresh(interaction)
                if not self.store.use_play(g, u, "race"):
                    self.store.add_candies(g, u, self.bet, "course-rembourse", boost=False)
                    self.state = "empty"
                    return await self.refresh(interaction)
                await interaction.response.defer()
                self.pick = index
                self.winner = random.randrange(len(RACERS))
                data = await asyncio.to_thread(race_gif, self.winner, tuple(r["name"] for r in RACERS),
                                               tuple(r["color"] for r in RACERS), random.randrange(6))
                won = self.pick == self.winner
                self.reward = grant(self.store, g, u, int(self.bet * PAYOUT) if won else 0, 12 if won else 4,
                                    "course", stats={"race_win": 1} if won else {"race_loss": 1})
                self.state = "racing"
                await self.refresh(interaction, attachments=[image_file(data, RACE_FILE)])
                await asyncio.sleep(3.9)
                self.state = "done"
                self.finish()
                await self.push()
        return cb


class Race(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["race"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.remaining(interaction.guild_id, interaction.user.id, "race") > 0
        await RaceView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="course", description="🧹 Course de balais : parie sur la bonne sorcière")
    @app_commands.guild_only()
    async def course(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Race(bot))
