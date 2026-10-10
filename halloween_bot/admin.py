"""Single, tidy /setup panel for Halloween Bot and automatic competitions.

Admin configures channel + role + announcement interval + registration window,
then presses one button. No /tournament_start/close/audit slash clutter.
"""
from __future__ import annotations

import csv
import io
import time
import zipfile
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .common import card, fail, authorized, themed_view


def _end_of_season():
    now = datetime.now(timezone.utc)
    halloween = datetime(now.year, 11, 1, tzinfo=timezone.utc)
    # After Halloween, launch a 14-day season rather than an expired event.
    return int((halloween if now < halloween else now + timedelta(days=14)).timestamp())


def setup_card(bot, guild):
    config = bot.round_store.config(guild.id)
    season = bot.competition.season(guild.id)
    return card(
        "Configuration Halloween",
        "🕸️ **Tout se règle depuis ce panneau.**\n"
        "Choisis un salon, un rôle à notifier, la fréquence des manches "
        "et le temps laissé pour s'inscrire.",
        theme="night",
        sections=[
            ("📢  SALON", f"<#{config['channel_id']}>" if config["channel_id"]
             else "❌ À choisir", True),
            ("🔔  RÔLE NOTIFIÉ",
             f"<@&{config['role_id']}>" if config["role_id"] else "❌ À choisir", True),
            ("⏰  ANNONCES", f"**Toutes les {config['interval_min']} min**", True),
            ("🎟️  INSCRIPTIONS", f"**{config['signup_min']} min**", True),
            ("💀  DÉFIS",
             "**10 min** après les inscriptions, automatiquement.", True),
            ("✅  ÉTAT",
             "🟢 Manches automatiques programmées" if config["enabled"]
             else "🟡 En attente de validation", True),
            ("🎁  PRIX",
             config["prize_label"] or "Aucun prix annoncé par le bot", False),
            ("📜  RÈGLEMENT",
             config["rules_url"] or "À ajouter si tu annonces un prix réel", False),
            ("🏆  SAISON",
             f"{'🟢 En cours' if season['status']=='active' else '🔒 Clôturée'} "
             f"jusqu'à <t:{season['ends_at']}:F>" if season else
             "Elle sera créée automatiquement après validation.", False),
        ],
        note="Une annonce mentionnera uniquement le rôle sélectionné, "
             "à l'ouverture de chaque manche. Les boutons restent accessibles "
             "après les redémarrages.",
    )


class ChannelPicker(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="📢 Salon des événements et des inscriptions",
            channel_types=[discord.ChannelType.text],
            row=0,
        )

    async def callback(self, interaction):
        channel = interaction.guild.get_channel(self.values[0].id)
        if not isinstance(channel, discord.TextChannel):
            return await fail(interaction, "Choisis un salon textuel.")
        member = interaction.guild.me
        perms = channel.permissions_for(member)
        if not (perms.view_channel and perms.send_messages and
                perms.embed_links and perms.read_message_history):
            return await fail(
                interaction, "Il me faut Voir le salon, Envoyer des messages, "
                "Intégrer des liens et Lire l'historique."
            )
        interaction.client.round_store.configure(
            interaction.guild.id, channel_id=channel.id
        )
        # Keep existing candy/ghost appearances using the same channel.
        interaction.client.store.set_channel(interaction.guild.id,channel.id)
        await interaction.response.edit_message(
            embed=setup_card(interaction.client, interaction.guild),
            view=self.view,
        )


class RolePicker(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="🔔 Rôle à mentionner lors de chaque manche",
            min_values=1, max_values=1, row=1,
        )

    async def callback(self, interaction):
        role = interaction.guild.get_role(self.values[0].id)
        if not role or role.is_default() or role.managed:
            return await fail(interaction, "Choisis un rôle normal du serveur.")
        interaction.client.round_store.configure(
            interaction.guild.id, role_id=role.id
        )
        await interaction.response.edit_message(
            embed=setup_card(interaction.client, interaction.guild),
            view=self.view,
        )


class IntervalPicker(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="⏰ Fréquence des événements",
            options=[
                discord.SelectOption(label="Toutes les 30 minutes",value="30",
                                     emoji="⏰"),
                discord.SelectOption(label="Toutes les heures",value="60",
                                     emoji="🕰️"),
                discord.SelectOption(label="Toutes les 2 heures",value="120",
                                     emoji="🌙"),
            ],
            row=2,
        )

    async def callback(self, interaction):
        interaction.client.round_store.configure(
            interaction.guild.id, interval_min=int(self.values[0])
        )
        await interaction.response.edit_message(
            embed=setup_card(interaction.client, interaction.guild),
            view=self.view,
        )


class SignupPicker(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="🎟️ Combien de temps pour s'inscrire ?",
            options=[
                discord.SelectOption(label="10 minutes",value="10",emoji="🎟️"),
                discord.SelectOption(label="30 minutes",value="30",emoji="⏳"),
            ],
            row=3,
        )

    async def callback(self, interaction):
        interaction.client.round_store.configure(
            interaction.guild.id, signup_min=int(self.values[0])
        )
        await interaction.response.edit_message(
            embed=setup_card(interaction.client, interaction.guild),
            view=self.view,
        )


class PrizeModal(discord.ui.Modal, title="🎁 Prix & règlement de la compétition"):
    prix = discord.ui.TextInput(
        label="Prix annoncé (facultatif)",
        placeholder="Exemple : 1 000 € — offert par les organisateurs",
        required=False, max_length=100,
    )
    reglement = discord.ui.TextInput(
        label="URL HTTPS du règlement (si un prix est annoncé)",
        placeholder="https://monsite.fr/reglement-halloween",
        required=False, max_length=400,
    )

    async def on_submit(self, interaction):
        if not authorized(interaction):
            return await fail(interaction, "Permission Gérer le serveur requise.")
        if self.prix.value and not self.reglement.value.startswith("https://"):
            return await fail(
                interaction, "Pour annoncer un prix réel, indique un règlement "
                "public accessible en HTTPS."
            )
        active = interaction.client.competition.season(interaction.guild.id)
        if active and active["status"] == "active":
            return await fail(
                interaction, "Le tournoi est déjà lancé : son prix ne peut pas "
                "être modifié au milieu de la saison."
            )
        try:
            interaction.client.round_store.configure(
                interaction.guild.id,
                prize_label=self.prix.value,
                rules_url=self.reglement.value,
            )
        except ValueError:
            return await fail(interaction, "Vérifie le lien HTTPS du règlement.")
        await interaction.response.send_message(
            embed=card("Prix enregistré",
                       "✅ Les informations sont enregistrées. "
                       "Retourne dans /setup pour valider la saison.",
                       theme="success"),
            ephemeral=True,
        )


class SetupView(discord.ui.View):
    def __init__(self, owner):
        super().__init__(timeout=900)
        self.owner = owner
        self.add_item(ChannelPicker())
        self.add_item(RolePicker())
        self.add_item(IntervalPicker())
        self.add_item(SignupPicker())
        themed_view(self)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner or not authorized(interaction):
            await fail(interaction, "Seul l'administrateur ayant ouvert ce panneau "
                       "peut utiliser ces boutons.")
            return False
        return True

    @discord.ui.button(
        label="Valider & programmer", emoji="🎃",
        style=discord.ButtonStyle.success, row=4,
    )
    async def save(self, interaction, button):
        guild = interaction.guild
        config = interaction.client.round_store.config(guild.id)
        if not config["channel_id"] or not config["role_id"]:
            return await fail(interaction, "Choisis d'abord le salon et le rôle.")
        channel = guild.get_channel(config["channel_id"])
        role = guild.get_role(config["role_id"])
        if not isinstance(channel, discord.TextChannel) or not role:
            return await fail(interaction, "Le salon ou le rôle n'existe plus.")
        bot_member = guild.me
        if not bot_member:
            return await fail(interaction, "Impossible de vérifier mes permissions.")
        perms = channel.permissions_for(bot_member)
        if not (perms.view_channel and perms.send_messages and
                perms.embed_links and perms.read_message_history):
            return await fail(interaction, "Permissions insuffisantes dans le salon.")
        if not role.mentionable and not perms.mention_everyone:
            return await fail(
                interaction, "Rends le rôle mentionnable, ou donne au bot "
                "l'autorisation de mentionner les rôles dans ce salon."
            )
        if config["prize_label"] and not config["rules_url"]:
            return await fail(interaction, "Un prix réel exige un règlement HTTPS.")
        season = interaction.client.competition.season(guild.id)
        if not season or season["status"] != "active":
            started = interaction.client.competition.start(
                guild.id, interaction.user.id, _end_of_season(),
                prize_label=config["prize_label"],
                rules_url=config["rules_url"],
            )
            if started["status"] != "started":
                return await fail(interaction,
                                  "Impossible de lancer la saison. "
                                  "Vérifie la date et les règles.")
        status = interaction.client.round_store.enable(guild.id)
        if status not in ("enabled", "already_enabled"):
            return await fail(interaction, "Configuration incomplète.")
        await interaction.response.edit_message(
            embed=setup_card(interaction.client,guild),
            view=self,
        )
        # The background loop will create the first round within 20 s.

    @discord.ui.button(
        label="Prix & règles", emoji="📜",
        style=discord.ButtonStyle.secondary, row=4,
    )
    async def prize(self, interaction, button):
        await interaction.response.send_modal(PrizeModal())

    @discord.ui.button(
        label="Rapport final", emoji="🏆",
        style=discord.ButtonStyle.secondary, row=4,
    )
    async def report(self, interaction, button):
        records, season = interaction.client.competition.audit(
            interaction.guild.id, limit=100000
        )
        if not season:
            return await fail(interaction, "Aucun résultat de saison à exporter.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        contents = io.StringIO()
        writer = csv.writer(contents)
        writer.writerow(["user_id","mode","jour_utc","debut","fin","resultat","points"])
        for row in records:
            writer.writerow([
                row["user_id"],row["mode"],row["utc_day"],
                row["started_at"],row["finished_at"] or "",
                row["outcome"],row["points"]
            ])
        data = io.BytesIO()
        filename = f"cup-audit-{interaction.guild.id}.csv"
        with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(filename, contents.getvalue().encode("utf-8-sig"))
        data.seek(0)
        await interaction.followup.send(
            f"📜 **{len(records)} tentatives enregistrées.** "
            "Vérifie les résultats, comptes et ex æquo avant toute remise "
            "de prix réel.",
            file=discord.File(data,filename=filename+".zip"),
            ephemeral=True,
        )


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup", description="⚙️ Configuration simple du bot Halloween"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction):
        if not authorized(interaction):
            return await fail(interaction, "Permission Gérer le serveur requise.")
        await interaction.response.send_message(
            embed=setup_card(self.bot,interaction.guild),
            view=SetupView(interaction.user.id),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
