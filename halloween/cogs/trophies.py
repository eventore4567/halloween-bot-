"""/succes — the 41 achievements, with progress bars for the locked ones."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E
from ..rewards import check_achievements, measures
from ..ui import GameView, Panel, nav

PER_PAGE = 9


class TrophyView(GameView):
    banner_key = "trophies"
    kicker = "SUCCÈS"
    owner_hint = "Ouvre tes propres succès avec /succes."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.page = 0
        self.fresh = check_achievements(self.store, self.guild_id, self.owner_id)

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        owned = self.store.owned(g, u)
        values = measures(self.store, g, u)
        done = sum(1 for a in config.ACHIEVEMENTS if "ach:" + a[0] in owned)
        total = len(config.ACHIEVEMENTS)
        p = Panel("gold").banner(self.banner_key)
        p.title("Tes succès", icon="trophy",
                body=f"{E.bar(done, total, 8)} **{done}/{total}** débloqués\n"
                     f"-# Chaque succès rapporte des bonbons une seule fois.")
        if self.fresh:
            p.text("\n".join(f"{E.sparkle} **Nouveau : {a[1]}** · +{config.fmt(a[6])} {E.candy}" for a in self.fresh))
            self.fresh = []
        p.sep()
        pages = (total + PER_PAGE - 1) // PER_PAGE
        chunk = config.ACHIEVEMENTS[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        lines = []
        for key, name, desc, emoji, measure, goal, reward in chunk:
            if "ach:" + key in owned:
                lines.append(f"{E(emoji)} **{name}** {E.check}\n-# {desc} · +{config.fmt(reward)} {E.candy}")
            else:
                have = min(values.get(measure, 0), goal)
                lines.append(f"{E.lock} **{name}** · {E.bar(have, goal, 5)} {config.short(have)}/{config.short(goal)}\n"
                             f"-# {desc} · +{config.fmt(reward)} {E.candy}")
        p.text("\n".join(lines))
        p.sep()
        prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self.page == 0)
        nxt = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self.page >= pages - 1)
        prev.callback = self._move(-1)
        nxt.callback = self._move(1)
        page = discord.ui.Button(label=f"Page {self.page + 1}/{pages}", style=discord.ButtonStyle.secondary,
                                 disabled=True)
        p.row(prev, page, nxt, nav("profile", self.owner_id, "Profil", "pumpkin_lit"))
        p.footer(self.footer())
        return p

    def _move(self, step):
        async def cb(interaction):
            self.page += step
            await self.refresh(interaction)
        return cb


class Trophies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["trophies"] = self.open

    async def open(self, interaction, edit=False):
        await TrophyView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="succes", description="🏆 Tes 41 succès et ta progression")
    @app_commands.guild_only()
    async def succes(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Trophies(bot))
