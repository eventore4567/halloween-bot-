"""/chasse — press-your-luck: dig graves for ghosts, cash out before the Reaper."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

ROWS, COLS = 4, 5
REAPERS = 3


def dig_value(digs: int) -> int:
    """Each new ghost is worth a bit more than the previous one."""
    return 12 + 6 * digs


def make_board(rnd=random):
    cells = ["reaper"] * REAPERS + ["chest"] + ["ghost"] * (ROWS * COLS - REAPERS - 1)
    rnd.shuffle(cells)
    return cells


class HuntView(GameView):
    banner_key = "hunt"
    kicker = "CHASSE AUX FANTÔMES"
    owner_hint = "Lance ta propre chasse avec /chasse."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.board = make_board()
        self.dug: list[int] = []
        self.pot = 0
        self.state = "play" if allowed else "empty"
        self.reward = None
        self.flash = ""

    def build(self) -> Panel:
        p = Panel("cyan").banner(self.banner_key)
        if self.state == "empty":
            p.title("Les tombes sont fermées pour aujourd'hui", icon="hourglass",
                    body=f"Le cimetière rouvre {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        safe_left = sum(1 for i, c in enumerate(self.board) if c != "reaper" and i not in self.dug)
        reapers_left = REAPERS
        risk = reapers_left / max(1, safe_left + reapers_left)
        if self.state == "dead":
            p.title("LA FAUCHEUSE !", icon="reaper",
                    body=f"Elle t'a attrapé… tu perds ton butin de **{config.fmt(self.pot)}** {E.candy}.\n"
                         f"{self.reward.line() if self.reward and self.reward.xp else ''}")
        elif self.state == "cashed":
            p.title("Tu t'enfuis avec le butin !", icon="candy_bag", body=self.reward.line())
        else:
            p.title("Creuse… si tu l'oses", icon="ghost",
                    body=f"Chaque {E.ghost} trouvé remplit ton sac. Le {E.chest} **double** ton butin. "
                         f"Mais **{REAPERS}** {E.reaper} Faucheuses dorment ici : si tu en réveilles une, tu perds tout !")
        p.text(f"{E.candy_bag} Butin : **{config.fmt(self.pot)}** {E.candy} · prochain fantôme "
               f"**+{dig_value(len(self.dug))}** · risque {E.bar(risk, 1, 5)} **{round(risk * 100)} %**"
               + (f"\n{self.flash}" if self.flash else ""))
        p.sep()
        over = self.state != "play"
        cells = []
        for i, kind in enumerate(self.board):
            shown = i in self.dug or over
            icon = {"reaper": "reaper", "chest": "chest", "ghost": "ghost_still"}[kind] if shown else "tomb"
            style = "secondary"
            if i in self.dug:
                style = "danger" if kind == "reaper" else "success"
            cells.append(button(None, icon, style, self._dig(i), disabled=shown))
        p.rows(cells, COLS)
        if over:
            left = self.store.remaining(self.guild_id, self.owner_id, "hunt")
            p.row(nav("hunt", self.owner_id, f"Rejouer ({left})", "ghost", "success"),
                  nav("memory", self.owner_id, "Mémoire", "eye"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        else:
            p.row(button(f"Encaisser {config.fmt(self.pot)} bonbons", "candy_bag", "success", self._cash,
                         disabled=self.pot <= 0))
        p.footer(self.footer())
        return p

    def _dig(self, i):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or i in self.dug:
                    return await interaction.response.defer()
                kind = self.board[i]
                self.dug.append(i)
                g, u = self.guild_id, self.owner_id
                if kind == "reaper":
                    self.state = "dead"
                    self.reward = grant(self.store, g, u, 0, 5, "chasse", stats={"hunt_dead": 1})
                    self.finish()
                elif kind == "chest":
                    self.pot = max(self.pot * 2, 40)
                    self.flash = f"{E.chest} **Coffre maudit !** Ton butin est doublé !"
                else:
                    gain = dig_value(len(self.dug) - 1)
                    self.pot += gain
                    self.flash = f"{E.ghost} Un fantôme ! **+{gain}**"
                if self.state == "play" and all(self.board[j] == "reaper" or j in self.dug
                                                for j in range(len(self.board))):
                    self._cash_out()
                await self.refresh(interaction)
        return cb

    def _cash_out(self):
        g, u = self.guild_id, self.owner_id
        self.state = "cashed"
        self.flash = ""
        self.reward = grant(self.store, g, u, self.pot, 8 + len(self.dug), "chasse", best={"hunt_best": self.pot})
        self.finish()

    async def _cash(self, interaction):
        async with self.lock:
            if self.state != "play" or self.pot <= 0:
                return await interaction.response.defer()
            self._cash_out()
            await self.refresh(interaction)

    def on_expire(self):
        if self.state == "play" and self.pot > 0:
            self._cash_out()
        elif self.state == "play":
            self.state = "cashed"
            self.reward = grant(self.store, self.guild_id, self.owner_id, 0, 0, "chasse")


class Hunt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["hunt"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "hunt")
        await HuntView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="chasse", description="👻 Chasse aux fantômes : creuse les tombes, évite la Faucheuse")
    @app_commands.guild_only()
    async def chasse(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Hunt(bot))
