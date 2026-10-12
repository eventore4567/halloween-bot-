"""/sort — cast a bad spell on a member to steal some of their candies."""
from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import Panel, banner_file, notice, relative


def loot_amount(target_candies: int) -> int:
    """8 % of the victim's pocket, between 20 and 400."""
    return max(20, min(400, int(target_candies * 0.08)))


class Curse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sort", description="💀 Jette un mauvais sort à un membre pour lui voler des bonbons")
    @app_commands.describe(cible="Ta victime")
    @app_commands.guild_only()
    async def sort(self, interaction: discord.Interaction, cible: discord.Member):
        s, g, u = self.bot.store, interaction.guild_id, interaction.user.id
        if cible.bot or cible.id == u:
            return await notice(interaction, "Choisis une vraie victime (pas toi-même, ni un bot) !")
        left = s.cooldown_left(g, u, "curse")
        if left:
            return await notice(interaction, f"Ta baguette recharge… prochain sort {relative(time.time() + left)}.",
                                icon="hourglass")
        protected = s.cooldown_left(g, cible.id, "cursed")
        if protected:
            return await notice(interaction, f"{cible.mention} est encore protégé(e) par la lune "
                                             f"jusqu'à {relative(time.time() + protected)}.", icon="moon")
        if s.candies(g, cible.id) < 100:
            return await notice(interaction, f"{cible.mention} n'a presque rien en poche… laisse-le tranquille !")
        try:
            s.spend(g, u, config.CURSE_COST, "sort")
        except NotEnough:
            return await notice(interaction, f"Un sort coûte **{config.CURSE_COST}** {E.candy}.")
        s.set_cooldown(g, u, "curse", config.CURSE_COOLDOWN)
        p = Panel("red").banner("curse")
        if s.use_item(g, cible.id, "amulet"):
            s.set_cooldown(g, cible.id, "cursed", config.CURSE_PROTECTION)
            p.title("Le sort rebondit sur une amulette !", icon="gem", thumb=E.url("gem"),
                    body=f"{interaction.user.mention} tente de maudire {cible.mention}… mais son "
                         f"{E.gem} **amulette** absorbe le sort et se brise. Raté !")
        elif random.random() < config.CURSE_SUCCESS:
            amount = loot_amount(s.candies(g, cible.id))
            try:
                s.transfer(g, cible.id, u, amount, reason="sort")
            except NotEnough:
                amount = 0
            s.set_cooldown(g, cible.id, "cursed", config.CURSE_PROTECTION)
            r = grant(s, g, u, 0, 10, "sort", stats={"curse_win": 1})
            p.title("Malédiction réussie !", icon="skull", thumb=E.url("skull_fire"),
                    body=f"{interaction.user.mention} maudit {cible.mention} et lui dérobe "
                         f"**{config.fmt(amount)}** {E.candy} !\n{r.line()}\n"
                         f"-# {cible.display_name} est protégé(e) pendant 2 h. Achète une "
                         f"{E.gem} amulette à la `/boutique` pour te protéger.")
        else:
            penalty = min(config.CURSE_COST, s.candies(g, u))
            if penalty:
                s.transfer(g, u, cible.id, penalty, reason="sort-retour")
            grant(s, g, u, 0, 3, "sort", stats={"curse_fail": 1})
            p.title("Le sort se retourne contre toi !", icon="cross", thumb=E.url("lightning"),
                    body=f"{interaction.user.mention} rate son sort… {cible.mention} récupère "
                         f"**{config.fmt(penalty)}** {E.candy} en dédommagement !")
        p.footer(f"Prochain sort de {interaction.user.display_name} dans 1 h · {config.CURSE_COST} bonbons le sort")
        view = discord.ui.LayoutView()
        view.add_item(p.container())
        await interaction.response.send_message(view=view, files=[await banner_file("curse")],
                                                allowed_mentions=discord.AllowedMentions(users=[cible]))


async def setup(bot):
    await bot.add_cog(Curse(bot))
