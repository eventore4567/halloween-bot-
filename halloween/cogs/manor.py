"""/manoir — idle game: haunt for souls, recruit monsters that farm for you."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import NotEnough
from ..emojis import E
from ..ui import GameView, Panel, button, nav, notice


class ManorView(GameView):
    banner_key = "manor"
    owner_hint = "Ouvre ton propre manoir avec /manoir."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=900)
        self.flash = ""
        state, offline = self.store.manor_tick(self.guild_id, self.owner_id)
        if offline >= 1:
            self.flash = (f"{E.moon} Pendant ton absence, tes monstres ont récolté "
                          f"**{config.short(offline)}** âmes !")
        self._milestones()

    def _milestones(self):
        paid = self.store.manor_claim_milestones(self.guild_id, self.owner_id)
        for threshold, reward in paid:
            self.flash += (f"\n{E.trophy} Palier **{config.short(threshold)} âmes** atteint : "
                           f"**+{config.fmt(reward)}** {E.candy} !")

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        st = self.store.manor(g, u)
        rate = self.store.manor_rate(st["units"])
        power = config.click_power(st["click_level"])
        rank, total = self.store.rank(g, u, "manor")
        p = Panel("purple").banner(self.banner_key)
        rank_txt = f"**{rank}{'er' if rank == 1 else 'e'}** sur {total}" if rank else "*pas encore classé*"
        p.title("Ton Manoir Hanté", icon="soul", thumb=E.url("soul"),
                body=f"{E.soul} En réserve : **{config.fmt(st['souls'])}** âmes\n"
                     f"{E.cauldron} Production : **{config.fmt(rate)}** par minute\n"
                     f"{E.ghost} Par hantise : **{config.fmt(power)}**\n"
                     f"{E.crown} Seigneurs du Manoir : {rank_txt}")
        idx = st["milestone"]
        if idx < len(config.MANOR_MILESTONES):
            goal = config.MANOR_MILESTONES[idx]
            p.text(f"{E.bar(st['lifetime'], goal, 8)} **{config.short(st['lifetime'])}** / {config.short(goal)} âmes "
                   f"récoltées\n-# Prochain palier : **+{config.MANOR_MILESTONE_REWARD[idx]}** {E.candy} · "
                   f"le classement compte toutes les âmes récoltées, dépenser ne te fait pas reculer !")
        if self.flash:
            p.text(self.flash.strip())
            self.flash = ""
        p.sep()
        owned = [(unit, st["units"].get(unit["key"], 0)) for unit in config.MANOR_UNITS]
        lines = [f"{E(unit['emoji'])} **{unit['name']}** ×{n} · +{config.fmt(unit['rate'] * n)}/min"
                 for unit, n in owned if n]
        p.text("### Tes monstres\n" + ("\n".join(lines) if lines else
               "Personne ne hante encore ces couloirs… Hante le manoir, puis recrute ton premier "
               f"{E.soul} **Feu follet** !"))
        p.sep()
        options = []
        for unit, n in owned:
            cost = config.unit_cost(unit["cost"], n)
            ok = st["souls"] >= cost
            options.append(discord.SelectOption(
                label=f"{unit['name']} — {config.short(cost)} âmes", value=unit["key"],
                emoji=E.partial(unit["emoji"]),
                description=f"+{config.fmt(unit['rate'])}/min · tu en as {n}" + ("" if ok else " · trop cher")))
        select = discord.ui.Select(placeholder="Recruter un monstre…", options=options)
        select.callback = self._recruit
        p.row(select)
        up_cost = config.click_upgrade_cost(st["click_level"])
        p.row(button(f"Hanter (+{config.short(power)})", "ghost", "success", self._haunt),
              button(f"Hantise ×2 · {config.short(up_cost)}", "lightning", "primary", self._upgrade,
                     disabled=st["souls"] < up_cost),
              nav("top_manor", self.owner_id, "Seigneurs", "trophy"))
        p.footer(self.footer("Seul toi peux hanter ce manoir"))
        return p

    async def _haunt(self, interaction):
        self.store.manor_tick(self.guild_id, self.owner_id, click=1)
        self._milestones()
        await self.refresh(interaction)

    async def _upgrade(self, interaction):
        try:
            cost = self.store.manor_upgrade_click(self.guild_id, self.owner_id)
        except NotEnough:
            return await notice(interaction, "Pas assez d'âmes pour renforcer ta hantise.")
        self.flash = f"{E.lightning} Ta hantise est deux fois plus puissante ! (-{config.short(cost)} âmes)"
        await self.refresh(interaction)

    async def _recruit(self, interaction):
        key = interaction.data["values"][0]
        unit = next(x for x in config.MANOR_UNITS if x["key"] == key)
        try:
            cost = self.store.manor_buy_unit(self.guild_id, self.owner_id, key)
        except NotEnough:
            await interaction.response.defer()
            self.flash = f"{E.cross} Il te faut plus d'âmes pour recruter un **{unit['name']}**."
            return await self.refresh(interaction)
        self.flash = (f"{E(unit['emoji'])} Un **{unit['name']}** rejoint ton manoir ! "
                      f"(-{config.short(cost)} âmes, +{config.fmt(unit['rate'])}/min)")
        self._milestones()
        await self.refresh(interaction)


class Manor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["manor"] = self.open

    async def open(self, interaction, edit=False):
        await ManorView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="manoir", description="🏚️ Ton manoir hanté : recrute des monstres qui récoltent des âmes")
    @app_commands.guild_only()
    async def manoir(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Manor(bot))
