"""🌾 Decorative, interactive pumpkin farm with real persistent harvests."""
from __future__ import annotations

import time
import discord
from discord import app_commands
from discord.ext import commands

from .common import OwnerView, card
from .storage import CROPS


def farm_card(bot, guild_id, user_id, notice=""):
    plot = bot.store.farm(guild_id, user_id)
    player = bot.store.profile(guild_id, user_id)
    crop = plot["crop"]
    level = plot["level"]

    if crop is None:
        state = "🕸️ **Terrain libre**\nChoisis une graine ci-dessous."
    elif plot["ready_at"] <= int(time.time()):
        state = f"✨ **{CROPS[crop][0]} prête !**\nAppuie sur Récolter."
    else:
        state = (
            f"🌱 **{CROPS[crop][0]} en croissance**\n"
            f"🕯️ Récolte possible <t:{plot['ready_at']}:R>."
        )

    panel = card(
        "Le potager hanté",
        "🌙 Bienvenue dans ton jardin, là où poussent les citrouilles les plus étranges.",
        theme="night",
        sections=[
            ("🌾  NIVEAU", f"**{level} / 5**", True),
            ("✨  RENDEMENT", f"**+{15 * (level - 1)} %**", True),
            ("🍬  TON PANIER", f"**{player['candies']:,}**", True),
            ("🎃  TA PLANTATION", state, False),
            ("🌱  CHOISIS TES GRAINES",
             "**🎃 Classique**\nGratuite · 8 min · 65 à 115 🍬\n\n"
             "**👻 Spectrale**\n45 🍬 · 15 min · 135 à 210 🍬\n\n"
             "**💀 Maudite**\n140 🍬 · 30 min · 290 à 420 🍬", False),
            ("🛠️  AMÉLIORER LE POTAGER",
             ("👑 Ton jardin est au niveau maximum !" if level >= 5
              else f"Prochain niveau : **{level * 450:,} 🍬**\n"
                   "Chaque niveau augmente les prochaines récoltes de 15 %."), False),
        ],
        note="Les plantations continuent de pousser même quand le bot redémarre.",
    )
    if notice:
        panel.add_field(name="🦇  DERNIÈRE ACTION", value=notice, inline=False)
    return panel


class FarmView(OwnerView):
    def __init__(self, owner_id):
        super().__init__(owner_id, timeout=300)

    async def respond(self, interaction, action=None, detail=None):
        g, u = interaction.guild.id, interaction.user.id
        if action == "plant":
            status = interaction.client.store.plant(g, u, detail)
            notice = {
                "planted": f"🌱 **{CROPS[detail][0]} plantée !** Reviens récolter.",
                "occupied": "🕸️ Récolte d'abord ta plantation actuelle.",
                "poor": "🍬 Tu n'as pas assez de bonbons pour cette graine.",
                "unknown": "💀 Cette graine n'existe pas.",
            }[status]
        elif action == "harvest":
            result = interaction.client.store.harvest(g, u)
            if result["status"] == "harvested":
                notice = f"✨ **+{result['amount']} bonbons !** Récolte réussie."
            elif result["status"] == "growing":
                notice = f"🕯️ Encore {result['seconds'] // 60 + 1} minute(s) de pousse."
            else:
                notice = "🕸️ Ton terrain est vide. Plante une graine."
        elif action == "upgrade":
            status, value = interaction.client.store.upgrade_farm(g, u)
            notice = {
                "upgraded": f"✨ Ton potager passe au **niveau {value}** !",
                "poor": f"🍬 Il faut **{value} bonbons** pour cet agrandissement.",
                "max": "👑 Ton potager est déjà au niveau maximum !",
            }[status]
        else:
            notice = ""
        await interaction.response.edit_message(
            embed=farm_card(interaction.client, g, u, notice),
            view=self,
        )

    @discord.ui.button(label="Classique", emoji="🎃", style=discord.ButtonStyle.success, row=0)
    async def pumpkin(self, interaction, button):
        await self.respond(interaction, "plant", "citrouille")

    @discord.ui.button(label="Spectrale", emoji="👻", style=discord.ButtonStyle.primary, row=0)
    async def ghost(self, interaction, button):
        await self.respond(interaction, "plant", "spectrale")

    @discord.ui.button(label="Maudite", emoji="💀", style=discord.ButtonStyle.danger, row=0)
    async def cursed(self, interaction, button):
        await self.respond(interaction, "plant", "maudite")

    @discord.ui.button(label="Récolter", emoji="🍬", style=discord.ButtonStyle.success, row=1)
    async def harvest(self, interaction, button):
        await self.respond(interaction, "harvest")

    @discord.ui.button(label="Améliorer", emoji="🛠️", style=discord.ButtonStyle.secondary, row=1)
    async def upgrade(self, interaction, button):
        await self.respond(interaction, "upgrade")


class Farming(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_farm(self, interaction):
        await interaction.response.send_message(
            embed=farm_card(self.bot, interaction.guild.id, interaction.user.id),
            view=FarmView(interaction.user.id),
            ephemeral=False,
        )

    @app_commands.command(name="farm", description="🌾 Cultiver et récolter des citrouilles")
    @app_commands.guild_only()
    async def farm(self, interaction: discord.Interaction):
        await self.send_farm(interaction)


async def setup(bot):
    await bot.add_cog(Farming(bot))
