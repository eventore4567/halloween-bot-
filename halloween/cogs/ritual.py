"""/rituel — Simon says with cursed symbols: memorise the formula, repeat it."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

SYMBOLS = [("candle", "Bougie", "danger"), ("skull", "Crâne", "secondary"),
           ("eye", "Œil", "success"), ("moon", "Lune", "primary")]
START_LEN = 3
MAX_ROUNDS = 8


def ritual_reward(rounds_done: int) -> int:
    """Sum of 15 × length of every formula completed."""
    return sum(15 * (START_LEN + r) for r in range(rounds_done))


class RitualView(GameView):
    banner_key = "ritual"
    owner_hint = "Lance ton propre rituel avec /rituel."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.sequence: list[int] = []
        self.typed: list[int] = []
        self.round = 0
        self.state = "ready" if allowed else "empty"
        self.reward = None
        self.flash = ""
        self.token = 0

    def build(self) -> Panel:
        p = Panel("purple").banner(self.banner_key)
        if self.state == "empty":
            p.title("Le grimoire est refermé", icon="book",
                    body=f"Plus de rituels aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        seq = " ".join(E(SYMBOLS[i][0]) for i in self.sequence)
        if self.state == "ready":
            p.title("Le Rituel", icon="book",
                    body="Une formule maudite va s'afficher quelques secondes. **Mémorise-la**, "
                         "puis répète-la symbole par symbole. Elle s'allonge à chaque manche !\n"
                         f"-# {MAX_ROUNDS} manches max · plus tu vas loin, plus tu gagnes")
            p.row(button("Commencer le rituel", "candle", "success", self._start))
        elif self.state == "show":
            p.title(f"Manche {self.round} · mémorise !", icon="eye",
                    body=f"# {seq}\n{E.hourglass} La formule s'efface dans un instant…")
        elif self.state == "input":
            typed = " ".join(E(SYMBOLS[i][0]) for i in self.typed)
            p.title(f"Manche {self.round} · à toi !", icon="book",
                    body=f"Répète la formule ({len(self.typed)}/{len(self.sequence)}) :\n# {typed or E.question}"
                         + (f"\n{self.flash}" if self.flash else ""))
            p.row(*[button(name, emoji, style, self._tap(i)) for i, (emoji, name, style) in enumerate(SYMBOLS)])
        else:
            done = self.round - (0 if self.state == "won" else 1)
            title = "Rituel parfait !" if self.state == "won" else "La formule est brisée…"
            p.title(title, icon="sparkle" if self.state == "won" else "skull",
                    body=(f"La bonne formule était :\n# {seq}\n" if self.state == "lost" else "")
                    + f"Manches réussies : **{done}/{MAX_ROUNDS}**\n{self.reward.line()}")
            left = self.store.remaining(self.guild_id, self.owner_id, "ritual")
            p.row(nav("ritual", self.owner_id, f"Rejouer ({left})", "book", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer("Seul toi peux réciter ce rituel"))
        return p

    async def _start(self, interaction):
        async with self.lock:
            if self.state != "ready":
                return await interaction.response.defer()
            await self._next_round(interaction)

    async def _next_round(self, interaction):
        self.round += 1
        self.sequence.append(random.randrange(len(SYMBOLS)))
        if self.round == 1:
            self.sequence += [random.randrange(len(SYMBOLS)) for _ in range(START_LEN - 1)]
        self.typed = []
        self.flash = ""
        self.state = "show"
        self.token += 1
        token = self.token
        await self.refresh(interaction)

        async def hide():
            await asyncio.sleep(1.6 + 0.45 * len(self.sequence))
            async with self.lock:
                if self.state == "show" and self.token == token:
                    self.state = "input"
                    await self.push()
        asyncio.create_task(hide())

    def _tap(self, index):
        async def cb(interaction):
            async with self.lock:
                if self.state != "input":
                    return await interaction.response.defer()
                self.typed.append(index)
                pos = len(self.typed) - 1
                if self.sequence[pos] != index:
                    self._end(won=False)
                    return await self.refresh(interaction)
                if len(self.typed) == len(self.sequence):
                    if self.round >= MAX_ROUNDS:
                        self._end(won=True)
                        return await self.refresh(interaction)
                    return await self._next_round(interaction)
                self.flash = f"{E.check} Continue…"
                await self.refresh(interaction)
        return cb

    def _end(self, won: bool):
        self.state = "won" if won else "lost"
        done = self.round if won else self.round - 1
        self.reward = grant(self.store, self.guild_id, self.owner_id, ritual_reward(done), 6 + 3 * done, "rituel",
                            best={"ritual_best": done})
        self.finish()

    def on_expire(self):
        if self.state in ("show", "input"):
            self._end(won=False)


class Ritual(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["ritual"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "ritual")
        await RitualView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="rituel", description="🕯️ Le Rituel : mémorise la formule maudite et répète-la")
    @app_commands.guild_only()
    async def rituel(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Ritual(bot))
