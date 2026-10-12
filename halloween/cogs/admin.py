"""/admin — server configuration for organisers (Manage Server permission)."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E, sync_emojis
from ..ui import Panel, notice


def panel_view(p: Panel) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView()
    v.add_item(p.container())
    return v


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Admin(commands.GroupCog, group_name="admin", group_description="Réglages de la Nuit Hantée (organisateurs)"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    def drops(self):
        return self.bot.get_cog("Drops")

    async def _reply(self, interaction, title, body, icon="check", color="green"):
        p = Panel(color).title(title, body, icon=icon)
        await interaction.response.send_message(view=panel_view(p), ephemeral=True)

    @app_commands.command(name="salon", description="Choisir le salon des apparitions (sacs, quiz éclair, boss)")
    @app_commands.describe(salon="Salon où les événements apparaissent")
    async def salon(self, interaction: discord.Interaction, salon: discord.TextChannel):
        perms = salon.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.view_channel and perms.attach_files):
            return await notice(interaction, f"Je ne peux pas écrire (ou envoyer d'images) dans {salon.mention}.")
        self.bot.store.guild_set(interaction.guild_id, drop_channel=salon.id, drops_on=1)
        if self.drops():
            self.drops().cfg_cache.pop(interaction.guild_id, None)
        await self._reply(interaction, "Salon des apparitions réglé",
                          f"Les événements apparaîtront dans {salon.mention} quand le serveur est actif.\n"
                          f"-# Utilise `/admin apparitions` pour régler la fréquence, `/admin lancer` pour tester.")

    @app_commands.command(name="apparitions", description="Activer/désactiver les apparitions et régler leur fréquence")
    @app_commands.describe(actif="Activer les apparitions automatiques",
                           messages="Environ tous combien de messages du serveur (10 à 500)")
    async def apparitions(self, interaction: discord.Interaction, actif: bool,
                          messages: app_commands.Range[int, 10, 500] = 40):
        self.bot.store.guild_set(interaction.guild_id, drops_on=int(actif), drop_every=messages)
        if self.drops():
            self.drops().cfg_cache.pop(interaction.guild_id, None)
            self.drops().goal.pop(interaction.guild_id, None)
        cfg = self.bot.store.guild(interaction.guild_id)
        where = f"<#{cfg['drop_channel']}>" if cfg["drop_channel"] else "*aucun salon (utilise `/admin salon`)*"
        await self._reply(interaction, "Apparitions " + ("activées" if actif else "désactivées"),
                          f"Salon : {where}\nFréquence : environ tous les **{messages}** messages "
                          f"(au plus une toutes les 4 minutes).")

    @app_commands.command(name="lancer", description="Faire apparaître un événement maintenant, dans ce salon")
    @app_commands.choices(type=[
        app_commands.Choice(name="Sac de bonbons", value="loot"),
        app_commands.Choice(name="Quiz éclair", value="quiz"),
        app_commands.Choice(name="Boss : le Roi Citrouille", value="boss"),
    ])
    async def lancer(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        drops = self.drops()
        if interaction.guild_id in drops.active:
            return await notice(interaction, "Un événement est déjà en cours sur ce serveur.")
        await interaction.response.defer(ephemeral=True)
        view = await drops.spawn(interaction.channel, type.value)
        text = f"{E.check} **{type.name}** lancé !" if view else f"{E.cross} Impossible d'écrire dans ce salon."
        await interaction.followup.send(text, ephemeral=True)

    @app_commands.command(name="bonbons", description="Ajouter ou retirer des bonbons à un membre")
    @app_commands.describe(membre="Le membre", montant="Positif pour ajouter, négatif pour retirer")
    async def bonbons(self, interaction: discord.Interaction, membre: discord.Member,
                      montant: app_commands.Range[int, -1_000_000, 1_000_000]):
        s, g = self.bot.store, interaction.guild_id
        if montant < 0:
            current = s.candies(g, membre.id)
            montant = -min(current, -montant)
        if montant:
            s.add_candies(g, membre.id, montant, f"admin:{interaction.user.id}", boost=False)
        await self._reply(interaction, "Solde modifié",
                          f"{membre.mention} : **{montant:+}** {E.candy} → **{config.fmt(s.candies(g, membre.id))}**")

    @app_commands.command(name="emojis", description="Re-synchroniser les emojis personnalisés du bot")
    async def emojis(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        report = await sync_emojis(self.bot, self.bot.store)
        await interaction.followup.send(
            f"{E.check} Emojis : {report['created']} créés, {report['updated']} mis à jour, "
            f"{report['kept']} déjà en place, {report['failed']} en échec.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
