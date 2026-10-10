"""One-time setup. No module toggles, no excessive configuration."""
import discord
from discord import app_commands
from discord.ext import commands

from .common import card,fail,authorized


class ChannelPicker(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="🕸️ Choisir le salon des apparitions",
                         channel_types=[discord.ChannelType.text])

    async def callback(self,interaction):
        if not authorized(interaction):
            return await fail(interaction,"Permission Gérer le serveur requise.")
        channel=interaction.guild.get_channel(self.values[0].id)
        if not isinstance(channel,discord.TextChannel):
            return await fail(interaction,"Choisis un salon textuel.")
        member=interaction.guild.me
        if not member:
            return await fail(interaction,"Impossible de vérifier mes permissions.")
        perms=channel.permissions_for(member)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            return await fail(interaction,
                "Il me faut les permissions Voir le salon, Envoyer des messages et Intégrer des liens.")
        interaction.client.store.set_channel(interaction.guild.id,channel.id)
        await interaction.response.edit_message(
            embed=card("CONFIGURATION TERMINÉE",
                f"✅ Salon des événements : {channel.mention}\n\n"
                "🎃 Les bonbons, les jeux, le potager et les classements sont prêts.\n"
                "👻 Des apparitions arrivent toutes les 20 minutes.\n\n"
                "🦇 Aucun autre réglage nécessaire !"),
            view=None)
        self.view.stop()


class SetupView(discord.ui.View):
    def __init__(self,owner):
        super().__init__(timeout=180)
        self.owner=owner
        self.add_item(ChannelPicker())

    async def interaction_check(self,interaction):
        if interaction.user.id!=self.owner or not authorized(interaction):
            await fail(interaction,"Seul l'administrateur ayant ouvert ce panneau peut l'utiliser.")
            return False
        return True


class Admin(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    @app_commands.command(name="setup",description="⚙️ Choisir le salon des événements Halloween")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def setup(self,interaction:discord.Interaction):
        if not authorized(interaction):
            return await fail(interaction,"Permission Gérer le serveur requise.")
        current=self.bot.store.configured_channel(interaction.guild.id)
        label=f"<#{current}>" if current else "Aucun"
        await interaction.response.send_message(
            embed=card("CONFIGURATION HALLOWEEN",
                f"🕸️ Salon actuel : **{label}**\n\n"
                "🎃 Sélectionne simplement le salon des apparitions.\n"
                "🍬 Toutes les autres fonctionnalités sont disponibles automatiquement."),
            view=SetupView(interaction.user.id),ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
