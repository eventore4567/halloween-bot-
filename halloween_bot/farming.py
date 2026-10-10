"""🌾 Interactive pumpkin farming, harvesting and persistent upgrades."""
from __future__ import annotations

import time
import discord
from discord import app_commands
from discord.ext import commands

from .common import OwnerView, card, fail
from .storage import CROPS


def farm_card(bot,guild_id,user_id,notice=""):
    data=bot.store.farm(guild_id,user_id)
    player=bot.store.profile(guild_id,user_id)
    crop=data["crop"]
    level=data["level"]
    if crop:
        name=CROPS[crop][0]
        if data["ready_at"]<=int(time.time()):
            state=f"✅ **{name} prête à récolter !**"
        else:
            state=f"🌱 **{name}** pousse jusqu'à <t:{data['ready_at']}:R>."
    else:
        state="🕸️ Terrain libre, choisis une graine ci-dessous."
    body=(
        "╭──────── 🌾 ────────╮\n"
        "**LE POTAGER HANTÉ**\n"
        "╰──────── 🎃 ────────╯\n\n"
        f"🏡 **Niveau du potager : {level}/5**\n"
        f"✨ Bonus de récolte : **+{15*(level-1)} %**\n"
        f"🍬 Ton panier : **{player['candies']:,} bonbons**\n\n"
        f"**État de la plantation**\n{state}\n\n"
        "🎃 Citrouille : **gratuit** · 8 min\n"
        "👻 Spectrale : **45 🍬** · 15 min\n"
        "💀 Maudite : **140 🍬** · 30 min\n\n"
        f"🛠️ Prochain agrandissement : "
        f"**{level*450 if level<5 else 'MAX'} 🍬**\n"
    )
    if notice:
        body += f"\n━━━━━━━━━━━━━━━━━━\n{notice}"
    return card("FERME HALLOWEEN",body,purple=True)


class FarmView(OwnerView):
    def __init__(self,owner_id):
        super().__init__(owner_id,timeout=300)

    async def respond(self,interaction,action=None,detail=None):
        g,u=interaction.guild.id,interaction.user.id
        if action=="plant":
            status=interaction.client.store.plant(g,u,detail)
            notice={
                "planted":f"🌱 **{CROPS[detail][0]} plantée !** Reviens récolter.",
                "occupied":"🕸️ Récolte d'abord ta plantation actuelle.",
                "poor":"🍬 Tu n'as pas assez de bonbons pour cette graine.",
                "unknown":"💀 Graine inconnue."
            }[status]
        elif action=="harvest":
            result=interaction.client.store.harvest(g,u)
            if result["status"]=="harvested":
                notice=f"🎉 Récolte réussie ! **+{result['amount']} bonbons**."
            elif result["status"]=="growing":
                notice=f"🕯️ Ta récolte pousse encore pendant {result['seconds']//60+1} minute(s)."
            else:
                notice="🕸️ Rien à récolter. Plante une citrouille."
        elif action=="upgrade":
            status,value=interaction.client.store.upgrade_farm(g,u)
            notice={
                "upgraded":f"✨ Potager amélioré au **niveau {value}** !",
                "poor":f"🍬 Il te manque des bonbons pour payer **{value} 🍬**.",
                "max":"👑 Ta ferme est déjà au niveau maximum !"
            }[status]
        else:
            notice=""
        await interaction.response.edit_message(
            embed=farm_card(interaction.client,g,u,notice),view=self)

    @discord.ui.button(label="Citrouille",emoji="🎃",style=discord.ButtonStyle.success,row=0)
    async def pumpkin(self,interaction,button):
        await self.respond(interaction,"plant","citrouille")

    @discord.ui.button(label="Spectrale",emoji="👻",style=discord.ButtonStyle.primary,row=0)
    async def ghost(self,interaction,button):
        await self.respond(interaction,"plant","spectrale")

    @discord.ui.button(label="Maudite",emoji="💀",style=discord.ButtonStyle.danger,row=0)
    async def cursed(self,interaction,button):
        await self.respond(interaction,"plant","maudite")

    @discord.ui.button(label="Récolter",emoji="🍬",style=discord.ButtonStyle.success,row=1)
    async def harvest(self,interaction,button):
        await self.respond(interaction,"harvest")

    @discord.ui.button(label="Améliorer",emoji="🛠️",style=discord.ButtonStyle.secondary,row=1)
    async def upgrade(self,interaction,button):
        await self.respond(interaction,"upgrade")


class Farming(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    async def send_farm(self,interaction):
        await interaction.response.send_message(
            embed=farm_card(self.bot,interaction.guild.id,interaction.user.id),
            view=FarmView(interaction.user.id),ephemeral=True)

    @app_commands.command(name="farm",description="🌾 Cultive des citrouilles et récolte des bonbons")
    @app_commands.guild_only()
    async def farm(self,interaction:discord.Interaction):
        await self.send_farm(interaction)


async def setup(bot):
    await bot.add_cog(Farming(bot))
