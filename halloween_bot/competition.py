"""🏆 Halloween Cup: season ranking, skill challenges and organizer controls.

These points are deliberately independent from random candy-farming games.
No entry fee, wagering, prize payouts or winner certification is implemented.
"""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .common import card, fail, icon, progress, themed_view, authorized
from .competition_store import (
    MODES, Competition, division, generate_puzzle, calendar_day,
)


def _human(guild, user_id):
    user = guild.get_member(user_id)
    return discord.utils.escape_markdown(user.display_name) if user else f"Joueur {user_id}"


def _head(season):
    return "🏆 HALLOWEEN CUP" if not season else "🏆 " + season["title"].upper()


def _reward(season):
    if not season or not season["prize_label"]:
        return "Aucun prix annoncé par l'organisateur."
    return (
        f"🎁 **{season['prize_label']}**\n"
        "Annonce de l'organisateur, non garantie par le bot."
    )


def top_lines(guild, rows):
    if not rows:
        return "🕸️ Aucun concurrent inscrit pour le moment."
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    result = []
    for row in rows:
        marker = medals.get(row["place"], f"**{row['place']:02}.**")
        line = (
            f"{marker} **{_human(guild, row['user_id'])}**\n"
            f"　└ **{row['score']:,} points** · {row['solved']} défis validés"
        )
        result.append(line)
    return "\n\n".join(result)


def top_card(bot, guild):
    season = bot.competition.season(guild.id)
    if not season:
        return card(
            "Classement du tournoi",
            "🕸️ Le tournoi n'a pas encore été lancé par un organisateur.",
            theme="night",
            note="Le classement des bonbons reste disponible dans /leaderboard.",
        )
    rows = bot.competition.standings(guild.id, 10)
    is_active = season["status"] == "active"
    status = (
        f"🟢 En cours · clôture <t:{season['ends_at']}:R>"
        if is_active else
        "🔒 Tournoi clôturé · résultats provisoires sous réserve de contrôle."
    )
    return card(
        "Classement de la saison",
        f"**{season['title']}**\n{status}",
        theme="gold",
        sections=[
            ("🏆  TOP 10 • POINTS DE COMPÉTITION", top_lines(guild, rows), False),
            ("🎁  RÉCOMPENSE ANNONCÉE", _reward(season), False),
        ],
        note="Égalité de points = même rang. "
             "Une finale ou un départage humain est nécessaire en cas d'égalité.",
    )


def rank_card(bot, guild, user):
    contest = bot.competition
    season = contest.season(guild.id)
    if not season:
        return card(
            "Mon rang",
            "🕸️ Aucun tournoi actif ou clôturé sur ce serveur.",
            theme="night",
        )
    entry = contest.position(guild.id, user.id)
    if not entry:
        return card(
            "Mon rang",
            f"🎃 {user.mention} ne participe pas encore à cette saison.",
            theme="night",
            note="Ouvre /competition puis utilise le bouton Participer.",
        )
    grade, next_level, _ = division(entry["score"])
    remain = max(0, next_level - entry["score"])
    used_today = 3 - len(contest.remaining_modes(guild.id, user.id))
    return card(
        "Ton rang dans l'arène",
        f"**{user.mention}**\nLa compétition est lancée.",
        theme="night",
        sections=[
            ("🏆  RANG", f"**#{entry['place']} / {entry['participants']}**", True),
            ("💎  POINTS", f"**{entry['score']:,}**", True),
            ("🧩  DÉFIS RÉUSSIS", f"**{entry['solved']}**", True),
            ("🦇  DIVISION", f"**{grade}**", True),
            ("🎯  PROCHAINE DIVISION",
             "**Sommet atteint !**" if remain == 0 else
             f"**{remain:,} points** à obtenir\n"
             f"{progress(entry['score'], next_level)}", True),
            ("⏳  TENTATIVES DU JOUR",
             f"**{used_today} / 3** utilisées · réinitialisation à 00:00 UTC", False),
        ],
        note="Les bonbons, les achats et les jeux de chance ne donnent aucun "
             "point dans le tournoi.",
    )


def rules_card(season):
    rules = season["rules_url"] if season else None
    prize = _reward(season)
    return card(
        "Règles du tournoi",
        "⚖️ **Compétition gratuite et fondée sur des défis de réflexion.**",
        theme="night",
        sections=[
            ("📜  COMMENT MARQUER",
             "🔮 Calcul : **100 points**\n"
             "📜 Mot maudit : **130 points**\n"
             "🗝️ Code de la crypte : **160 points**", False),
            ("⏳  LIMITES",
             "Une seule tentative de chaque épreuve par jour UTC. "
             "100 secondes maximum pour répondre. "
             "Un mauvais résultat ou un abandon consomme la tentative.", False),
            ("🚫  INTERDIT",
             "Automatisation, comptes multiples, manipulation d'API, "
             "exploitation de bugs et achats de points.", False),
            ("🏆  CLASSEMENT",
             "Points uniquement pour les réponses correctes. "
             "Les égalités donnent le même rang et exigent un départage humain.", False),
            ("🎁  PRIX", prize, False),
            ("🔗  RÈGLEMENT COMPLET",
             rules if rules else
             "Les organisateurs doivent publier les conditions officielles "
             "avant d'annoncer un prix réel.", False),
        ],
        note="Le bot ne verse aucun prix. Toute attribution réelle doit être "
             "contrôlée et effectuée par l'organisateur.",
    )


def competition_card(bot, guild, user):
    season = bot.competition.season(guild.id)
    if not season:
        return card(
            "Halloween Cup",
            "🌙 Une arène hantée attend ses premiers compétiteurs...",
            theme="night",
            sections=[
                ("🏆  SAISON", "En attente de lancement.", False),
                ("🦇  POUR LES JOUEURS",
                 "Tous les jeux Halloween classiques restent disponibles.", False),
                ("⚙️  POUR LES ORGANISATEURS",
                 "Utilise /tournament_start pour lancer une compétition gratuite "
                 "avec une date de fin et des règles publiques.", False),
            ],
        )
    entry = bot.competition.position(guild.id, user.id)
    grade = division(entry["score"])[0] if entry else "Non inscrit"
    joined = "✅ Inscrit" if entry else "🕸️ Pas encore inscrit"
    is_active = season["status"] == "active"
    return card(
        "Halloween Cup",
        "🏆 **Le classement qui compte vraiment.**\n"
        "Les meilleurs joueurs gagnent des points en relevant des défis, "
        "pas en ouvrant des citrouilles au hasard.",
        theme="gold" if is_active else "night",
        sections=[
            ("🏆  ÉTAT DE LA SAISON",
             f"{'🟢 EN COURS' if is_active else '🔒 TERMINÉE'}\n"
             f"{season['title']}\n"
             f"Fin prévue : <t:{season['ends_at']}:F> · <t:{season['ends_at']}:R>",
             False),
            ("🎃  TA PARTICIPATION", joined, True),
            ("💎  TA DIVISION", grade, True),
            ("🧩  TROIS ÉPREUVES QUOTIDIENNES",
             "🔮 **Calcul** · 100 pts\n"
             "📜 **Mot maudit** · 130 pts\n"
             "🗝️ **Code de la crypte** · 160 pts\n\n"
             "Un seul essai par épreuve et par jour.", False),
            ("🎁  RÉCOMPENSE ANNONCÉE", _reward(season), False),
        ],
        note="Si un prix réel est proposé, l'organisateur doit vérifier "
             "l'éligibilité et les scores avant de désigner un gagnant.",
        thumbnail=True,
    )


class AnswerModal(discord.ui.Modal):
    def __init__(self, attempt_id, guild_id, owner_id):
        super().__init__(title="🗝️ Réponse • Halloween Cup", timeout=180)
        self.attempt_id = attempt_id
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.answer_input = discord.ui.TextInput(
            label="Ta réponse",
            placeholder="Écris le nombre ou le mot trouvé",
            style=discord.TextStyle.short,
            required=True,
            max_length=120,
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction):
        if interaction.user.id != self.owner_id:
            return await fail(interaction, "Ce défi ne t'appartient pas.")
        result = interaction.client.competition.answer(
            self.attempt_id,
            self.guild_id,
            self.owner_id,
            self.answer_input.value,
        )
        status = result["status"]
        if status == "correct":
            entry = interaction.client.competition.position(
                self.guild_id, self.owner_id
            )
            panel = card(
                "Défi remporté",
                "✨ **Bonne réponse !** Une étoile éclaire ton grimoire.",
                theme="success",
                sections=[
                    ("🏆  POINTS GAGNÉS", f"**+{result['points']}**", True),
                    ("💎  TOTAL DE SAISON", f"**{entry['score']:,}**", True),
                    ("🥇  POSITION", f"**#{entry['place']}**", True),
                ],
                note="Retrouve les autres épreuves dans /challenge.",
            )
        elif status == "incorrect":
            panel = card(
                "Défi échoué",
                "🕷️ **Ce n'est pas la bonne réponse.**",
                theme="danger",
                sections=[
                    ("💀  POINTS", "**+0**", False),
                    ("🕯️  PROCHAIN ESSAI",
                     "Demain après 00:00 UTC pour cette épreuve.", False),
                ],
            )
        else:
            descriptions = {
                "expired": "⏳ Le temps imparti est écoulé, ou le tournoi a fermé.",
                "used": "🕸️ Cette épreuve a déjà été soumise.",
                "forbidden": "🔒 Ce défi ne t'appartient pas.",
            }
            panel = card(
                "Défi indisponible",
                descriptions.get(status, "Le défi ne peut plus être validé."),
                theme="night",
            )
        await interaction.response.send_message(embed=panel, ephemeral=True)


class AnswerView(discord.ui.View):
    def __init__(self, owner_id, guild_id, attempt_id, expires_at):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.attempt_id = attempt_id
        self.expires_at = expires_at
        themed_view(self)

    @discord.ui.button(
        label="Répondre au défi", emoji="🗝️",
        style=discord.ButtonStyle.success,
    )
    async def answer(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await fail(interaction, "Ce défi ne t'appartient pas.")
        if int(time.time()) >= self.expires_at:
            return await fail(interaction, "Le défi a expiré.")
        await interaction.response.send_modal(
            AnswerModal(self.attempt_id, self.guild_id, self.owner_id)
        )


class ChallengeView(discord.ui.View):
    def __init__(self, bot, guild_id, owner_id):
        super().__init__(timeout=240)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.bot = bot
        remaining = bot.competition.remaining_modes(guild_id, owner_id)
        for mode, settings in MODES.items():
            button = discord.ui.Button(
                label=f"{settings['title'].split(' ', 1)[1]} · {settings['points']} pts",
                emoji=settings["emoji"],
                disabled=mode not in remaining,
                style=discord.ButtonStyle.primary if mode in remaining
                else discord.ButtonStyle.secondary,
            )
            async def begin(interaction, selected=mode):
                if interaction.user.id != self.owner_id:
                    return await fail(interaction, "Ce panneau appartient à un autre joueur.")
                prompt, answer = generate_puzzle(selected)
                issued = self.bot.competition.issue(
                    self.guild_id, self.owner_id, selected, prompt, answer
                )
                if issued["status"] != "issued":
                    reasons = {
                        "closed": "Le tournoi n'est plus ouvert.",
                        "join_first": "Inscris-toi avec /competition avant de jouer.",
                        "already_today": "Ce défi a déjà été tenté aujourd'hui.",
                    }
                    return await fail(interaction, reasons.get(issued["status"],
                                                             "Défi indisponible."))
                panel = card(
                    MODES[selected]["title"],
                    "🌙 Le chronomètre tourne. Lis l'énigme puis clique sur Répondre.",
                    theme="night",
                    sections=[
                        ("🧩  TON ÉPREUVE PERSONNELLE", issued["puzzle"], False),
                        ("🏆  POINTS EN JEU", f"**{issued['points']}**", True),
                        ("⏳  DATE LIMITE",
                         f"<t:{issued['expires_at']}:R>", True),
                    ],
                    note="Une seule réponse et une seule tentative. "
                         "Le défi est consommé même si tu quittes ce panneau.",
                )
                await interaction.response.send_message(
                    embed=panel,
                    view=AnswerView(
                        self.owner_id, self.guild_id,
                        issued["attempt_id"], issued["expires_at"]
                    ),
                    ephemeral=True,
                )
                # Refresh buttons for other challenges without trying to edit
                # a previously sent ephemeral response.
                button.disabled = True
            button.callback = begin
            self.add_item(button)
        themed_view(self)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await fail(interaction, "Ce panneau appartient à un autre joueur.")
            return False
        return True


class CompetitionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        themed_view(self)

    @discord.ui.button(
        label="Participer", emoji="✅", style=discord.ButtonStyle.success, row=0
    )
    async def join(self, interaction, button):
        result = interaction.client.competition.join(
            interaction.guild.id, interaction.user.id
        )
        if result == "welcome":
            text = "✨ **Inscription confirmée !** Tu peux désormais jouer."
        elif result == "joined":
            text = "🦇 Tu es déjà inscrit pour cette saison."
        else:
            return await fail(interaction, "Les inscriptions ne sont pas ouvertes.")
        await interaction.response.send_message(
            embed=card("Inscription Halloween Cup", text, theme="success",
                       note="Participation gratuite. Une personne par compte ; "
                            "les organisateurs devront vérifier les résultats."),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Défis", emoji="🧩", style=discord.ButtonStyle.primary, row=0
    )
    async def challenges(self, interaction, button):
        if not interaction.client.competition.entry(
            interaction.guild.id, interaction.user.id
        ):
            return await fail(interaction, "Inscris-toi d'abord avec Participer.")
        available = interaction.client.competition.remaining_modes(
            interaction.guild.id, interaction.user.id
        )
        season = interaction.client.competition.season(interaction.guild.id)
        if not season or season["status"] != "active":
            return await fail(interaction, "La saison est terminée.")
        await interaction.response.send_message(
            embed=card(
                "Le sanctuaire des défis",
                "🗝️ **Chaque joueur reçoit des énigmes différentes.**",
                theme="night",
                sections=[
                    ("📜  DISPONIBILITÉ",
                     "\n".join(
                         f"{'✅' if mode in available else '🔒'} "
                         f"{item['title']} — **{item['points']} points**"
                         for mode, item in MODES.items()
                     ), False),
                    ("⏳  RÉINITIALISATION",
                     "Chaque jour à **00:00 UTC**.", False),
                ],
                note="Clique sur un bouton pour commencer : la tentative sera "
                     "immédiatement enregistrée.",
            ),
            view=ChallengeView(
                interaction.client, interaction.guild.id, interaction.user.id
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Top 10", emoji="🏆", style=discord.ButtonStyle.secondary, row=0
    )
    async def top(self, interaction, button):
        await interaction.response.send_message(
            embed=top_card(interaction.client, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Mon rang", emoji="💎", style=discord.ButtonStyle.secondary, row=1
    )
    async def rank(self, interaction, button):
        await interaction.response.send_message(
            embed=rank_card(interaction.client, interaction.guild, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Règlement", emoji="📜", style=discord.ButtonStyle.secondary, row=1
    )
    async def rules(self, interaction, button):
        season = interaction.client.competition.season(interaction.guild.id)
        await interaction.response.send_message(
            embed=rules_card(season),
            ephemeral=True,
        )


class CompetitionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="competition", description="🏆 La compétition officielle Halloween"
    )
    @app_commands.guild_only()
    async def competition(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=competition_card(self.bot, interaction.guild, interaction.user),
            view=CompetitionView(),
        )

    @app_commands.command(
        name="challenge", description="🧩 Trois épreuves compétitives par jour"
    )
    @app_commands.guild_only()
    async def challenge(self, interaction: discord.Interaction):
        entry = self.bot.competition.entry(
            interaction.guild.id, interaction.user.id
        )
        if entry is None:
            return await fail(interaction, "Inscris-toi via /competition avant de jouer.")
        season = self.bot.competition.season(interaction.guild.id)
        if not season or season["status"] != "active":
            return await fail(interaction, "La compétition est actuellement fermée.")
        available = self.bot.competition.remaining_modes(
            interaction.guild.id, interaction.user.id
        )
        await interaction.response.send_message(
            embed=card(
                "Les trois épreuves",
                "🎯 **Fais travailler ton cerveau, pas ta chance !**",
                theme="night",
                sections=[
                    ("🧩  DÉFIS AUJOURD'HUI",
                     "\n".join(
                         f"{'✅' if mode in available else '🔒'} "
                         f"{entry['title']} · **{entry['points']} pts**"
                         for mode, entry in MODES.items()
                     ), False),
                ],
                note="Une tentative par épreuve et par jour UTC. "
                     "Lancer le défi consomme la tentative.",
            ),
            view=ChallengeView(
                self.bot, interaction.guild.id, interaction.user.id
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="competition_top", description="🏆 Top 10 de la saison"
    )
    @app_commands.guild_only()
    async def competition_top(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=top_card(self.bot, interaction.guild)
        )

    @app_commands.command(
        name="competition_rank", description="💎 Ton rang et ta division"
    )
    @app_commands.guild_only()
    async def competition_rank(self, interaction: discord.Interaction,
                               membre: discord.Member | None = None):
        await interaction.response.send_message(
            embed=rank_card(self.bot, interaction.guild, membre or interaction.user)
        )

    @app_commands.command(
        name="tournament_start", description="⚙️ Lancer la compétition (organisateurs)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        fin="Dernier jour du tournoi en UTC : AAAA-MM-JJ",
        prix="Prix annoncé par les organisateurs (facultatif)",
        reglement="Lien HTTPS du règlement, obligatoire en cas de prix",
    )
    async def tournament_start(
        self,
        interaction: discord.Interaction,
        fin: str,
        prix: str = "",
        reglement: str = "",
    ):
        if not authorized(interaction):
            return await fail(interaction, "Permission Gérer le serveur requise.")
        try:
            ending = datetime.strptime(fin, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            ) + timedelta(days=1)
        except ValueError:
            return await fail(interaction, "Format attendu : AAAA-MM-JJ.")
        outcome = self.bot.competition.start(
            interaction.guild.id,
            interaction.user.id,
            int(ending.timestamp()),
            prize_label=prix,
            rules_url=reglement,
        )
        if outcome["status"] != "started":
            reasons = {
                "bad_date": "Choisis une fin future, entre demain et dans 62 jours.",
                "rules_required": "Un prix annoncé exige un lien HTTPS vers "
                                  "le règlement officiel du tournoi.",
                "already_running": "Un tournoi est déjà en cours sur ce serveur.",
            }
            return await fail(interaction, reasons.get(outcome["status"],
                                                      "Impossible de démarrer."))
        await interaction.response.send_message(
            embed=card(
                "Halloween Cup lancée",
                "🏆 **La saison est officiellement ouverte !**",
                theme="success",
                sections=[
                    ("⏳  FIN", f"<t:{int(ending.timestamp())}:F>", False),
                    ("🎁  PRIX",
                     prix or "Aucun prix réel configuré.", False),
                    ("🦇  PARTICIPER",
                     "Les membres utilisent /competition pour rejoindre l'arène.", False),
                ],
                note="Les points sont désormais calculés indépendamment des bonbons.",
            ),
            ephemeral=True,
        )
        channel_id = self.bot.store.configured_channel(interaction.guild.id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(
                    embed=competition_card(self.bot, interaction.guild,
                                           interaction.user),
                    view=CompetitionView(),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                pass

    @app_commands.command(
        name="tournament_close", description="🔒 Clore la saison (organisateurs)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def tournament_close(self, interaction: discord.Interaction):
        if not authorized(interaction):
            return await fail(interaction, "Permission Gérer le serveur requise.")
        if not self.bot.competition.close(interaction.guild.id):
            return await fail(interaction, "Aucune saison active à clôturer.")
        await interaction.response.send_message(
            embed=card(
                "Saison clôturée",
                "🔒 **Les classements sont gelés.**",
                theme="night",
                sections=[
                    ("🏆  SUITE",
                     "Exporte l'historique avec /tournament_audit, "
                     "contrôle les comptes et départage les égalités avant "
                     "d'annoncer un gagnant.", False),
                ],
                note="La clôture ne déclenche aucun paiement.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="tournament_audit", description="📜 Exporter les essais de la saison (organisateurs)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def tournament_audit(self, interaction: discord.Interaction):
        if not authorized(interaction):
            return await fail(interaction, "Permission Gérer le serveur requise.")
        rows, season = self.bot.competition.audit(interaction.guild.id)
        if not season:
            return await fail(interaction, "Aucune saison à auditer.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "user_id", "epreuve", "jour_utc", "commence_unix",
            "termine_unix", "resultat", "points",
        ])
        for row in rows:
            writer.writerow([
                row["user_id"], row["mode"], row["utc_day"],
                row["started_at"], row["finished_at"] or "",
                row["outcome"], row["points"],
            ])
        data = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        filename = f"halloween-audit-{interaction.guild.id}-{season['season_id']}.csv"
        await interaction.followup.send(
            content=f"📜 **{len(rows)} tentatives exportées** "
                    "(maximum 5 000 lignes).\n"
                    "Contrôle les éventuels comptes multiples, les comportements "
                    "anormaux et les égalités avant toute remise de prix.",
            file=discord.File(data, filename=filename),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(CompetitionCog(bot))
