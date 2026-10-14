"""/reglages — server configuration for organisers (Manage Server permission)."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..emojis import E, sync_emojis
from ..ui import Panel, fetch_member, notice
from .reminder import tz_name


def panel_view(p: Panel) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView()
    v.add_item(p.container())
    return v


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Admin(commands.GroupCog, group_name="reglages", group_description="Réglages de la Nuit Hantée (réservé aux organisateurs du serveur)"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    def drops(self):
        return self.bot.get_cog("Drops")

    async def _reply(self, interaction, title, body, icon="check", color="green"):
        p = Panel(color).title(title, body, icon=icon)
        await interaction.response.send_message(view=panel_view(p), ephemeral=True)

    @app_commands.command(name="salon-evenements", description="Choisir le salon où apparaissent les événements : sacs de bonbons, quiz éclair, Roi Citrouille")
    @app_commands.describe(salon="Le salon où les événements du serveur vont apparaître")
    async def salon(self, interaction: discord.Interaction, salon: discord.TextChannel):
        perms = salon.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.view_channel and perms.attach_files):
            return await notice(interaction, f"Je ne peux pas écrire (ou envoyer d'images) dans {salon.mention}.")
        self.bot.store.guild_set(interaction.guild_id, drop_channel=salon.id, drops_on=1)
        if self.drops():
            self.drops().cfg_cache.pop(interaction.guild_id, None)
        await self._reply(interaction, "Salon des apparitions réglé",
                          f"Les événements apparaîtront dans {salon.mention} quand le serveur est actif.\n"
                          f"-# Utilise `/reglages frequence-evenements` pour régler la fréquence, `/reglages lancer-evenement` pour tester.")

    @app_commands.command(name="frequence-evenements", description="Activer ou couper les événements automatiques et régler leur fréquence")
    @app_commands.describe(actif="Activer les apparitions automatiques",
                           messages="Environ tous combien de messages du serveur (10 à 500)")
    async def apparitions(self, interaction: discord.Interaction, actif: bool,
                          messages: app_commands.Range[int, 10, 500] = 40):
        self.bot.store.guild_set(interaction.guild_id, drops_on=int(actif), drop_every=messages)
        if self.drops():
            self.drops().cfg_cache.pop(interaction.guild_id, None)
            self.drops().goal.pop(interaction.guild_id, None)
        cfg = self.bot.store.guild(interaction.guild_id)
        where = f"<#{cfg['drop_channel']}>" if cfg["drop_channel"] else "*aucun salon (utilise `/reglages salon-evenements`)*"
        await self._reply(interaction, "Apparitions " + ("activées" if actif else "désactivées"),
                          f"Salon : {where}\nFréquence : environ tous les **{messages}** messages "
                          f"(au plus une toutes les 4 minutes).")

    @app_commands.command(name="lancer-evenement", description="Faire apparaître un événement tout de suite, dans ce salon")
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

    @app_commands.command(name="lancer-malediction", description="Lancer tout de suite la Malédiction contagieuse sur un joueur")
    @app_commands.describe(membre="Qui reçoit la malédiction (par défaut : un joueur actif au hasard, ou toi)")
    async def malediction(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        cog = self.bot.get_cog("Contagion")
        if cog.state(interaction.guild_id):
            return await notice(interaction, "Une malédiction est déjà en cours (`/malediction`).")
        target = membre
        if target is None:
            drops = self.drops()
            seen = list(drops.authors.get(interaction.guild_id, {})) if drops else []
            random.shuffle(seen)
            target = interaction.user
            for uid in seen[:8]:
                member = await fetch_member(interaction.guild, uid)
                if cog.eligible(interaction.guild_id, member):
                    target = member
                    break
        if not cog.eligible(interaction.guild_id, target):
            return await notice(interaction, f"{target.mention} n'a encore jamais joué : la malédiction ne peut pas le toucher.")
        await interaction.response.defer(ephemeral=True)
        ok = await cog.start(interaction.guild, target, interaction.channel)
        await interaction.followup.send(f"{E.check} Malédiction lancée sur {target.mention} !" if ok
                                        else f"{E.cross} Impossible de lancer la malédiction.", ephemeral=True)

    @app_commands.command(name="lancer-chasse-tresor", description="Lancer une Chasse au trésor de 24 h dans tout le serveur")
    async def tresor(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("Treasure")
        await interaction.response.defer(ephemeral=True)
        cfg = self.bot.store.guild(interaction.guild_id)
        channel = (interaction.guild.get_channel(cfg["drop_channel"]) if cfg["drop_channel"] else None) \
            or interaction.channel  # the configured channel may have been deleted
        error = await cog.start(interaction.guild, channel)
        await interaction.followup.send(f"{E.cross} {error}" if error else
                                        f"{E.check} La Chasse au trésor est lancée dans {channel.mention} !",
                                        ephemeral=True)

    @app_commands.command(name="episode-suivant", description="Diffuser tout de suite le prochain épisode de la Série hantée")
    async def episode(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok = await self.bot.get_cog("Series").release(interaction.guild)
        await interaction.followup.send(f"{E.check} Épisode diffusé dans le salon des événements !" if ok else
                                        f"{E.cross} Règle d'abord le salon avec `/reglages salon-evenements`.",
                                        ephemeral=True)

    @app_commands.command(name="modifier-bonbons", description="Ajouter ou retirer des bonbons à un membre")
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

    @app_commands.command(name="heure-rappel", description="Heure du rappel quotidien du calendrier (pour les membres qui l'ont activé)")
    @app_commands.describe(heure="Heure de 0 à 23, dans le fuseau du bot (Europe/Paris par défaut)")
    async def heure_rappel(self, interaction: discord.Interaction, heure: app_commands.Range[int, 0, 23]):
        self.bot.store.meta_set(f"remind_hour:{interaction.guild_id}", heure)
        await self._reply(interaction, "Heure du rappel enregistrée",
                          f"Chaque jour à **{heure} h** ({tz_name()}), les membres qui ont activé `/rappel` seront prévenus "
                          f"dans le salon des événements (ou en message privé s'il n'y en a pas).")

    @app_commands.command(name="recharger-emojis", description="Renvoyer les emojis du bot sur Discord (s'ils ne s'affichent pas)")
    async def emojis(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        report = await sync_emojis(self.bot, self.bot.store)
        await interaction.followup.send(
            f"{E.check} Emojis : {report['created']} créés, {report['updated']} mis à jour, "
            f"{report['kept']} déjà en place, {report['failed']} en échec.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
