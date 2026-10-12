"""/donner — offer candies to another member (daily cap to avoid abuse)."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import Panel, notice


class Gift(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="donner", description="🎁 Offre des bonbons à un membre")
    @app_commands.describe(membre="À qui offrir ?", montant="Combien de bonbons ?")
    @app_commands.guild_only()
    async def donner(self, interaction: discord.Interaction, membre: discord.Member,
                     montant: app_commands.Range[int, 1, 100000]):
        s, g, u = self.bot.store, interaction.guild_id, interaction.user.id
        if membre.bot or membre.id == u:
            return await notice(interaction, "Offre tes bonbons à un vrai membre (pas à toi-même, ni à un bot) !")
        cap = config.LIMITS["gift_out"]
        if not s.bump(g, u, "gift_out", cap, amount=montant):
            left = max(0, cap - s.counter(g, u, "gift_out"))
            return await notice(interaction, f"Tu peux encore offrir **{config.fmt(left)}** bonbons aujourd'hui "
                                             f"(maximum {config.fmt(cap)} par jour).")
        try:
            s.transfer(g, u, membre.id, montant)
        except NotEnough:
            s.bump(g, u, "gift_out", amount=-montant)
            return await notice(interaction, f"Tu n'as pas **{config.fmt(montant)}** bonbons.")
        reward = grant(s, g, u, 0, 0, "don", stats={"gifts": 1})
        view = discord.ui.LayoutView()
        p = Panel("orange")
        p.title("Un cadeau d'Halloween !", icon="gift", thumb=E.url("gift"),
                body=f"{interaction.user.mention} offre **{config.fmt(montant)}** {E.candy} à {membre.mention} !\n"
                     f"{E.heart} Quelle générosité monstrueuse." + (f"\n{reward.line()}" if reward.line() else ""))
        p.footer(f"{membre.mention} a maintenant **{config.fmt(s.candies(g, membre.id))}** {E.candy}")
        view.add_item(p.container())
        await interaction.response.send_message(view=view, allowed_mentions=discord.AllowedMentions(users=[membre]))


async def setup(bot):
    await bot.add_cog(Gift(bot))
