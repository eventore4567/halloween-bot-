"""/memoire — classic pairs game on a 4×4 grid of buttons."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content.games import MEMORY_SYMBOLS
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

PAIRS = 8


def memory_reward(moves: int) -> int:
    """Perfect game (8 moves) = 240 candies, then -12 per extra move, min 40."""
    return max(40, 240 - 12 * max(0, moves - PAIRS))


class MemoryView(GameView):
    banner_key = "memory"
    owner_hint = "Lance ta propre partie avec /memoire."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=240)
        symbols = random.sample(MEMORY_SYMBOLS, PAIRS)
        self.grid = symbols * 2
        random.shuffle(self.grid)
        self.found: set[int] = set()
        self.open: list[int] = []
        self.moves = 0
        self.state = "play" if allowed else "empty"
        self.reward = None

    def build(self) -> Panel:
        p = Panel("cyan").banner(self.banner_key)
        if self.state == "empty":
            p.title("Plus de parties aujourd'hui", icon="hourglass",
                    body=f"Ta mémoire a besoin de repos. Reviens {relative(config.next_midnight_ts())} !")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        pairs = len(self.found) // 2
        if self.state == "won":
            p.title("Toutes les paires trouvées !", icon="sparkle",
                    body=f"En **{self.moves}** coups. {self.reward.line()}")
        elif self.state == "lost":
            p.title("Le temps est écoulé…", icon="hourglass",
                    body=f"Tu as trouvé **{pairs}/{PAIRS}** paires. Les tombes se referment.")
        else:
            p.title("Retrouve les 8 paires", icon="eye",
                    body=f"Retourne deux tombes à la fois. Moins tu fais de coups, plus tu gagnes de {E.candy} "
                         f"(jusqu'à **{memory_reward(PAIRS)}**).")
        p.text(f"{E.bar(pairs, PAIRS, 8)} Paires **{pairs}/{PAIRS}** · Coups **{self.moves}** · "
               f"Gain actuel **{memory_reward(max(self.moves, PAIRS))}** {E.candy}")
        p.sep()
        cells = []
        done = self.state != "play"
        for i, sym in enumerate(self.grid):
            shown = i in self.found or i in self.open or done
            style = "success" if i in self.found else ("primary" if i in self.open else "secondary")
            cells.append(button(None, sym if shown else "tomb", style, self._flip(i),
                                disabled=shown or done or len(self.open) >= 2))
        p.rows(cells, 4)
        if done:
            left = self.store.remaining(self.guild_id, self.owner_id, "memory")
            p.row(nav("memory", self.owner_id, f"Rejouer ({left})", "eye", "success"),
                  nav("hunt", self.owner_id, "Chasse aux fantômes", "ghost"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer("Seul toi peux jouer"))
        return p

    def _flip(self, i):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or i in self.open or i in self.found or len(self.open) >= 2:
                    return await interaction.response.defer()
                self.open.append(i)
                if len(self.open) < 2:
                    return await self.refresh(interaction)
                self.moves += 1
                a, b = self.open
                if self.grid[a] == self.grid[b]:
                    self.found.update(self.open)
                    self.open = []
                    if len(self.found) == len(self.grid):
                        self._win()
                    return await self.refresh(interaction)
                await self.refresh(interaction)
                await asyncio.sleep(1.3)
                self.open = []
                await self.push()
        return cb

    def _win(self):
        self.state = "won"
        g, u = self.guild_id, self.owner_id
        self.reward = grant(self.store, g, u, memory_reward(self.moves), 20, "memoire", stats={"memory_win": 1})
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self.state = "lost"


class Memory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["memory"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "memory")
        await MemoryView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="memoire", description="👁️ Mémoire d'outre-tombe : retrouve les 8 paires")
    @app_commands.guild_only()
    async def memoire(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Memory(bot))
