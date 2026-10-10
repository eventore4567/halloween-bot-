"""CRYPT CUP visual identity — Discord Components V2 (discord.py >= 2.6).

Standalone UI system for competition, seasonal podium, and round registration.
Unlike ordinary embeds, containers provide real visual grouping, accent bars,
spacers and dedicated buttons. Nothing relies on guild-specific emojis.
"""
from __future__ import annotations

import discord

from .common import fail, icon, progress, button_icon

VIOLET = discord.Color(0x7953D2)
AMBER = discord.Color(0xEB9D40)
SCARLET = discord.Color(0xBD4C63)
JADE = discord.Color(0x45AA8B)
GOLD = discord.Color(0xE0B75A)

def text(content):
    return discord.ui.TextDisplay(str(content))

def divider():
    return discord.ui.Separator(spacing=discord.SeparatorSpacing.small)

def container(*parts, accent=VIOLET):
    return discord.ui.Container(*parts, accent_color=accent)

def header(kicker, title, subtitle=""):
    return text(
        f"-# ✦  {kicker.upper()}  •  SAISON D'HALLOWEEN\n"
        f"## {title}\n"
        + (f"{subtitle}\n" if subtitle else "")
    )

def medal(n):
    return {1:"🥇",2:"🥈",3:"🥉"}.get(n, f"`{n:02}`")

def contest_board(bot, guild, user, buttons):
    """One image plus one native row, WITHOUT Discord's grey Container card.

    Discord does not support interactive controls over pixels in a
    MediaGallery. Both items are top-level Components V2 siblings instead
    of being nested in a Container: this removes the large theme-coloured
    slab, its padding, and the accent bar surrounding the image.
    The real buttons remain immediately under the image, on one row.
    """
    from .scene import SCENE_URI

    season = bot.competition.season(guild.id)
    round_info = bot.round_store.current(guild.id)
    entry = bot.competition.position(guild.id, user.id)
    state = (
        "Saison non ouverte" if not season
        else "Saison terminée" if season["status"] != "active"
        else "Inscriptions ouvertes"
        if round_info and round_info["status"] == "signup"
        else "Manche en cours"
        if round_info and round_info["status"] == "active"
        else "Entre deux manches"
    )
    place = f"#{entry['place']}" if entry else "non classé"
    points = entry["score"] if entry else 0
    description = (
        "CRYPT CUP, le Sanctuaire des Ombres. "
        f"État : {state}. Rang : {place}. Score : {points} points. "
        "Défis : Alchimie 100 points, Mots maudits 130 points, "
        "Code de la crypte 160 points. "
        "Actions accessibles juste sous l'image : "
        "Participer, Mes défis, Top 10, Mon rang, Règlement."
    )
    return (
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=SCENE_URI, description=description),
        ),
        discord.ui.ActionRow(*buttons),
    )


def podium_board(bot, guild):
    season=bot.competition.season(guild.id)
    leaders=bot.competition.standings(guild.id,10) if season else []
    lines=[]
    for item in leaders:
        name=f"<@{item['user_id']}>"
        lines.append(
            f"{medal(item['place'])} **{name}**  ·  **{item['score']:,} points** "
            f"\n　　-# {item['solved']} épreuve(s) validée(s)"
        )
    status=(
        "🟣 Saison ouverte" if season and season["status"]=="active"
        else "🔒 Résultats provisoires" if season
        else "🌫️ Saison non lancée"
    )
    return container(
        header("CRYPT CUP • TABLEAU D'HONNEUR",
               "LES NOMS GRAVÉS DANS LA PIERRE",
               "Chaque point doit être mérité."),
        divider(),
        text(f"**{status}**\n"
             + (f"Fin prévue : <t:{season['ends_at']}:F>"
                if season else "Attends la prochaine compétition.")),
        divider(),
        text("### 🏆 CLASSEMENT DE SAISON\n"
             + ("\n\n".join(lines) if lines else
                "🕸️ Aucun concurrent pour l'instant.")),
        divider(),
        text("-# Égalité de points = même rang. Le prix réel exige une "
             "vérification des résultats et de l'éligibilité par l'organisateur."),
        accent=GOLD,
    )


class CompetitionHome(discord.ui.LayoutView):
    """One unified interactive V2 panel with a panoramic uploaded banner."""

    def __init__(self, bot, guild, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild.id
        buttons = [
            discord.ui.Button(
                label="Participer", emoji=button_icon("key"),
                style=discord.ButtonStyle.success,
            ),
            discord.ui.Button(
                label="Mes défis", emoji=button_icon("book"),
                style=discord.ButtonStyle.primary,
            ),
            discord.ui.Button(
                label="Top 10", emoji=button_icon("trophy"),
                style=discord.ButtonStyle.secondary,
            ),
            discord.ui.Button(
                label="Mon rang", emoji=button_icon("crown"),
                style=discord.ButtonStyle.secondary,
            ),
            discord.ui.Button(
                label="Règlement", emoji=button_icon("book"),
                style=discord.ButtonStyle.secondary,
            ),
        ]
        for button, handler in zip(
            buttons, (self.register, self.play, self.top, self.rank, self.rules)
        ):
            button.callback = handler
        for component in contest_board(bot, guild, user, buttons):
            self.add_item(component)

    async def register(self, interaction):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Le portail appartient à un autre serveur.")
        if interaction.user.bot:
            return await fail(interaction, "Réservé aux membres du serveur.")
        round_info = self.bot.round_store.current(self.guild_id)
        if not round_info or round_info["status"] != "signup":
            return await fail(
                interaction,
                "Les inscriptions ne sont pas ouvertes. "
                "Attends la prochaine annonce dans le salon configuré.",
            )
        result = self.bot.round_store.join(
            round_info["id"], self.guild_id, interaction.user.id
        )
        if result == "joined":
            self.bot.competition.join(self.guild_id, interaction.user.id)
            return await interaction.response.send_message(
                "🎟️ **Ton inscription est confirmée !** "
                f"Le portail se referme <t:{round_info['signup_ends_at']}:R>.",
                ephemeral=True,
            )
        if result == "already_joined":
            return await fail(interaction, "Tu es déjà inscrit à cette manche.")
        await fail(interaction, "Les inscriptions sont terminées.")

    async def play(self, interaction):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Cette arène appartient à un autre serveur.")
        state, _ = self.bot.round_store.check(
            self.guild_id, interaction.user.id
        )
        if state != "ready":
            return await fail(
                interaction, "Inscris-toi à une manche, "
                "puis attends le début pour jouer.",
            )
        from .competition import ChallengeView
        from .competition_store import MODES
        available = self.bot.competition.remaining_modes(
            self.guild_id, interaction.user.id
        )
        if not available:
            return await fail(
                interaction, "Tu as utilisé tes défis du jour. "
                "Reviens demain à 00:00 UTC.",
            )
        await interaction.response.send_message(
            content=(
                "🗝️ **Choisis une épreuve du sanctuaire**\n"
                + "\n".join(
                    f"• {MODES[name]['title']} — {MODES[name]['points']} points"
                    for name in available
                )
            ),
            view=ChallengeView(self.bot, self.guild_id, interaction.user.id),
            ephemeral=True,
        )

    async def top(self, interaction):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Cette arène appartient à un autre serveur.")
        await interaction.response.send_message(
            view=PodiumView(self.bot, interaction.guild),
            ephemeral=True,
        )

    async def rank(self, interaction):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Cette arène appartient à un autre serveur.")
        from .competition import rank_card
        await interaction.response.send_message(
            embed=rank_card(self.bot, interaction.guild, interaction.user),
            ephemeral=True,
        )

    async def rules(self, interaction):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Cette arène appartient à un autre serveur.")
        from .competition import rules_card
        await interaction.response.send_message(
            embed=rules_card(self.bot.competition.season(self.guild_id)),
            ephemeral=True,
        )

class PodiumView(discord.ui.LayoutView):
    def __init__(self,bot,guild):
        super().__init__(timeout=300)
        self.add_item(podium_board(bot,guild))


class RoundSignupLayout(discord.ui.LayoutView):
    def __init__(self,bot,row,count):
        super().__init__(timeout=None)
        self.bot=bot
        self.round_id=row["id"]
        deadline=row["signup_ends_at"]
        self.add_item(container(
            header("CRYPT CUP • APPEL AUX CHASSEURS",
                   "LE PORTAIL DU CIMETIÈRE",
                   "Le silence se brise. Une nouvelle manche commence bientôt."),
            divider(),
            text("### 🎟️ LE REGISTRE DES VIVANTS\n"
                 f"👥 **{count} inscrit(s)**\n"
                 f"⏳ **Fermeture <t:{deadline}:R>** • <t:{deadline}:t>\n"
                 "🌙 **Une manche de 10 minutes** suivra automatiquement."),
            divider(),
            text("### ⚔️ COMMENT GAGNER ?\n"
                 "① Clique sur **Participer** pendant le compte à rebours.\n"
                 "② Attends l'ouverture de la crypte.\n"
                 "③ Résous une épreuve individuelle pour gagner des points.\n\n"
                 "-# Une seule participation par membre et par manche."),
            accent=AMBER,
        ))
        button=discord.ui.Button(
            label="INSCRIRE MON NOM",emoji="🎟️",
            style=discord.ButtonStyle.success,
            custom_id=f"halloween:round:join:{row['id']}"
        )
        button.callback=self.join
        self.add_item(container(
            text("### 🕯️ LE REGISTRE EST OUVERT"),
            discord.ui.ActionRow(button),
            accent=JADE,
        ))

    async def join(self,interaction):
        if not interaction.guild or interaction.user.bot:
            return await fail(interaction,"Réservé aux joueurs du serveur.")
        status=self.bot.round_store.join(self.round_id,
                                         interaction.guild.id,
                                         interaction.user.id)
        if status=="closed":
            return await fail(interaction,"Les inscriptions sont terminées.")
        if status=="already_joined":
            return await fail(interaction,"Ton nom est déjà inscrit !")
        self.bot.competition.join(interaction.guild.id,interaction.user.id)
        row=self.bot.round_store.round(self.round_id)
        await interaction.response.edit_message(
            view=RoundSignupLayout(self.bot,row,
                   self.bot.round_store.count(self.round_id)),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class RoundActiveLayout(discord.ui.LayoutView):
    def __init__(self,bot,row,count):
        super().__init__(timeout=None)
        self.bot=bot
        self.round_id=row["id"]
        self.add_item(container(
            header("CRYPT CUP • ÉPREUVE",
                   "LA CRYPTE EST OUVERTE",
                   "Les inscriptions sont scellées. Les épreuves commencent."),
            divider(),
            text(f"### 💀 LE RITUEL EST LANCÉ\n"
                 f"👥 **{count} chasseurs inscrits**\n"
                 f"⏳ Fin de l'épreuve : **<t:{row['ends_at']}:R>**\n"
                 "⚔️ **Une épreuve par manche** — jusqu'à 3 par jour UTC."),
            divider(),
            text("### 🗝️ CHOISIS TON DESTIN\n"
                 "🔮 Alchimie : **100 points**\n"
                 "📜 Grimoire : **130 points**\n"
                 "🗝️ Crypte : **160 points**\n\n"
                 "-# Seuls les membres inscrits pendant l'appel peuvent jouer."),
            accent=SCARLET,
        ))
        button=discord.ui.Button(
            label="ENTRER DANS LA CRYPTE",emoji="⚔️",
            style=discord.ButtonStyle.primary,
            custom_id=f"halloween:round:play:{row['id']}"
        )
        button.callback=self.play
        self.add_item(container(
            text("### ⏳ LE COMPTE À REBOURS TOURNE"),
            discord.ui.ActionRow(button),
            accent=VIOLET,
        ))

    async def play(self,interaction):
        if not interaction.guild:
            return await fail(interaction,"Cet événement appartient à un serveur.")
        state,row=self.bot.round_store.check(interaction.guild.id,interaction.user.id)
        if not row or row["id"]!=self.round_id or state!="ready":
            return await fail(interaction,
                "Tu dois être inscrit pendant l'appel pour jouer cette manche.")
        from .competition import ChallengeView
        from .competition_store import MODES
        available=self.bot.competition.remaining_modes(interaction.guild.id,
                                                        interaction.user.id)
        if not available:
            return await fail(interaction,
                              "Toutes tes épreuves ont déjà été utilisées aujourd'hui.")
        await interaction.response.send_message(
            content="🗝️ **Choisis une épreuve**\n"
                  +"\n".join(
                    f"• {MODES[m]['title']} — **{MODES[m]['points']} points**"
                    for m in available),
            view=ChallengeView(self.bot,interaction.guild.id,interaction.user.id),
            ephemeral=True,
        )


class RoundEndedLayout(discord.ui.LayoutView):
    def __init__(self,row,standings):
        super().__init__(timeout=None)
        entries=[]
        for rank,item in enumerate(standings[:5],1):
            entries.append(
                f"{medal(rank)} <@{item['user_id']}>  •  **{item['score']} pts**"
            )
        self.add_item(container(
            header("CRYPT CUP • TOMBEAU DES VAINQUEURS",
                   "LE VERDICT DES OMBRES",
                   "Le portail se ferme. La pierre retient les noms des plus forts."),
            divider(),
            text("### 🏆 CLASSEMENT DE LA MANCHE\n"
                 +("\n\n".join(entries) if entries else
                   "🕸️ Aucun joueur n'a marqué pendant cette manche.")),
            divider(),
            text("### 🌙 LA SUITE\n"
                 "Les points sont conservés pour le classement de saison. "
                 "Une autre manche sera annoncée selon la fréquence choisie.\n\n"
                 "-# Les résultats définitifs d'un prix réel doivent être "
                 "vérifiés par les organisateurs."),
            accent=GOLD,
        ))
