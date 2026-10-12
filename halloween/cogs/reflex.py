"""/reflexe — wait for the ghost, then click as fast as possible (3 rounds)."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

ROUNDS = 3


def reflex_points(seconds: float | None) -> int:
    if seconds is None:
        return 0
    if seconds < 0.7:
        return 70
    if seconds < 1.0:
        return 50
    if seconds < 1.5:
        return 32
    if seconds < 2.5:
        return 18
    return 8


def verdict(seconds: float | None) -> str:
    if seconds is None:
        return f"{E.cross} trop tôt !"
    if seconds < 0.7:
        return f"{E.lightning} **{seconds:.2f} s** — foudroyant !"
    if seconds < 1.0:
        return f"{E.fire} **{seconds:.2f} s** — très rapide"
    if seconds < 1.5:
        return f"{E.check} **{seconds:.2f} s** — pas mal"
    return f"{E.hourglass} **{seconds:.2f} s** — un peu lent"


class ReflexView(GameView):
    banner_key = "reflex"
    owner_hint = "Teste tes propres réflexes avec /reflexe."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=240)
        self.state = "ready" if allowed else "empty"
        self.round = 0
        self.times: list[float | None] = []
        self.shown_at = 0.0
        self.token = 0
        self.reward = None
        self.flash = ""

    def build(self) -> Panel:
        p = Panel("cyan").banner(self.banner_key)
        if self.state == "empty":
            p.title("Tes réflexes ont besoin de sommeil", icon="hourglass",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        results = "\n".join(f"`Manche {i + 1}` {verdict(t)}" for i, t in enumerate(self.times))
        if self.state == "ready":
            p.title("Réflexe du fantôme", icon="ghost",
                    body=f"Quand le bouton devient **vert**, clique le plus vite possible !\n"
                         f"Si tu cliques **avant**, la manche est perdue. {ROUNDS} manches.")
            p.row(button("Je suis prêt", "lightning", "primary", self._begin))
        elif self.state == "wait":
            p.title(f"Manche {self.round}/{ROUNDS} · attends…", icon="eye",
                    body=(results + "\n\n" if results else "") + f"{E.hourglass} *Le fantôme rôde… ne clique pas encore !*")
            p.row(button("… pas encore …", "lock", "secondary", self._early))
        elif self.state == "go":
            p.title(f"Manche {self.round}/{ROUNDS} · MAINTENANT !", icon="ghost",
                    body=(results + "\n\n" if results else "") + f"# {E.ghost} ATTRAPE-LE !")
            p.row(button("ATTRAPER !", "ghost", "success", self._catch))
        else:
            p.title("Résultats", icon="trophy", body=f"{results}\n\n{self.reward.line()}")
            left = self.store.remaining(self.guild_id, self.owner_id, "reflex")
            p.row(nav("reflex", self.owner_id, f"Rejouer ({left})", "lightning", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer("Seul toi peux jouer"))
        return p

    async def _begin(self, interaction):
        async with self.lock:
            if self.state != "ready":
                return await interaction.response.defer()
            await self._wait_round(interaction)

    async def _wait_round(self, interaction=None):
        self.round += 1
        self.state = "wait"
        self.token += 1
        token = self.token
        if interaction:
            await self.refresh(interaction)
        else:
            await self.push()

        async def appear():
            await asyncio.sleep(random.uniform(1.8, 4.5))
            async with self.lock:
                if self.state == "wait" and self.token == token:
                    self.state = "go"
                    await self.push()
                    self.shown_at = time.monotonic()
        asyncio.create_task(appear())

    async def _early(self, interaction):
        async with self.lock:
            if self.state != "wait":
                return await interaction.response.defer()
            self.times.append(None)
            await interaction.response.defer()
            await self._after_round()

    async def _catch(self, interaction):
        async with self.lock:
            if self.state != "go":
                return await interaction.response.defer()
            elapsed = max(0.05, time.monotonic() - self.shown_at)
            self.times.append(elapsed)
            await interaction.response.defer()
            await self._after_round()

    async def _after_round(self):
        if self.round >= ROUNDS:
            self._finish()
            await self.push()
        else:
            await self._wait_round()

    def _finish(self):
        self.state = "done"
        valid = [t for t in self.times if t is not None]
        total = sum(reflex_points(t) for t in self.times)
        self.reward = grant(self.store, self.guild_id, self.owner_id, total, 4 + 3 * len(valid), "reflexe",
                            stats={"reflex_games": 1})
        self.finish()

    def on_expire(self):
        if self.state in ("wait", "go"):
            while len(self.times) < ROUNDS:
                self.times.append(None)
            self._finish()


class Reflex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["reflex"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "reflex")
        await ReflexView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="reflexe", description="⚡ Réflexe du fantôme : clique dès qu'il apparaît")
    @app_commands.guild_only()
    async def reflexe(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Reflex(bot))
