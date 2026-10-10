"""Halloween quiz arena — original Components V2 game with four responsive buttons.

A proper question card with large typography, difficulty, live deadline,
optional film still, safe concurrency, and visibly colored right answer after
completion. No scores are awarded to the cash-prize tournament.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .common import fail, pretty, wait_text
from .quiz_content import DIFFICULTIES, generate_question, generate_film
from .visuals import AMBER, SCARLET, JADE, VIOLET, text, divider, header, container

LOG = logging.getLogger(__name__)


class MultipleChoice(discord.ui.LayoutView):
    """One shared room quiz, with first correct answer winning virtual candy."""

    def __init__(self, guild_id, data, *, film=False):
        super().__init__(timeout=data["time"])
        self.guild_id = guild_id
        self.data = data
        self.film = film
        self.finished = False
        self.message = None
        self.respondents = set()
        self._lock = asyncio.Lock()
        self.deadline = int(time.time()) + data["time"]
        self._build()

    def _build(self, outcome=None, winner=None):
        self.clear_items()
        data = self.data
        level = DIFFICULTIES[data["difficulty"]]["label"]
        title = "L'ÉCRAN MAUDIT" if self.film else "LE GRIMOIRE DES ÉPREUVES"
        teaser = (
            "Reconnais l'image avant que le projecteur ne s'éteigne."
            if self.film else
            "Quatre réponses, une seule vérité. Le grimoire ne pardonne pas."
        )
        accent = (
            JADE if outcome == "win"
            else SCARLET if outcome == "timeout"
            else VIOLET
        )
        heading = (
            "🎬 SÉANCE CINÉMA" if self.film
            else "🧩 QUIZ DES TÉNÈBRES"
        )
        intro = (
            f"✅ **Bonne réponse de {winner.mention} !**"
            if outcome == "win" and winner else
            "⌛ **TEMPS ÉCOULÉ — LA RÉPONSE EST RÉVÉLÉE !**"
            if outcome == "timeout" else
            teaser
        )
        parts = [
            header(heading, title, intro),
            divider(),
            text(
                f"### ❖ LA QUESTION\n"
                f"**{pretty(data['question'])}**\n\n"
                f"🎯 **{level}**　 ·　 🍬 **{data['reward']} bonbons**\n"
                f"⏳ **{'Épreuve terminée' if outcome else f'Fin <t:{self.deadline}:R>'}**"
            ),
        ]
        if self.film and data.get("image"):
            parts.extend([
                divider(),
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(
                        media=data["image"],
                        description="Photogramme de film d'horreur classique",
                    )
                ),
            ])
        if outcome:
            answer_index = data["correct"]
            answer = data["answers"][answer_index]
            parts.extend([
                divider(),
                text(
                    f"### {'🏆 VICTOIRE' if outcome=='win' else '🕯️ FIN DU TEMPS'}\n"
                    f"✅ **Réponse {chr(65 + answer_index)} · {answer}**\n"
                    + (
                        f"🎁 **+{data['reward']} bonbons** pour {winner.mention}"
                        if outcome=="win" and winner else
                        "🌫️ Aucun bonbon remporté."
                    )
                ),
            ])
            if self.film:
                parts.extend([
                    divider(),
                    text(
                        f"-# 🎬 Film sorti en {data['year']} • "
                        f"[Source de l'image sur Wikimedia Commons]({data['source']})"
                    ),
                ])
        else:
            parts.extend([
                divider(),
                text("### 🎮 À TOI DE JOUER\n"
                     "-# Choisis **une seule réponse**. "
                     "Une mauvaise tentative ne peut pas être rejouée."),
            ])
        self.add_item(container(*parts, accent=accent))
        choices = []
        for i, option in enumerate(data["answers"]):
            letter = "ABCD"[i]
            btn = discord.ui.Button(
                label=f"{letter}  ·  {option}"[:80],
                emoji=None,
                style=(
                    discord.ButtonStyle.success
                    if outcome and i == data["correct"]
                    else discord.ButtonStyle.secondary
                    if outcome else
                    discord.ButtonStyle.primary
                ),
                custom_id=f"crypt:quiz:{letter}:{self.deadline}",
                disabled=bool(outcome),
            )

            async def choose(interaction, selection=i):
                await self.choose(interaction, selection)

            btn.callback = choose
            choices.append(btn)
        self.add_item(container(
            text("### 🕷️ LES QUATRE PORTES"),
            discord.ui.ActionRow(*choices[:2]),
            discord.ui.ActionRow(*choices[2:]),
            accent=JADE if outcome == "win" else AMBER,
        ))

    async def choose(self, interaction, selected):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Le quiz appartient à un autre serveur.")
        if interaction.user.bot:
            return await fail(interaction, "Réservé aux membres.")
        async with self._lock:
            if self.finished or int(time.time()) >= self.deadline:
                return await fail(interaction, "Le quiz est déjà terminé.")
            if interaction.user.id in self.respondents:
                return await fail(interaction, "Une seule tentative par joueur.")
            self.respondents.add(interaction.user.id)
            if selected != self.data["correct"]:
                return await fail(interaction, "❌ Mauvaise réponse ! Tu es éliminé de ce quiz.")
            self.finished = True
            interaction.client.store.award(
                self.guild_id, interaction.user.id,
                self.data["reward"], quizzes=1,
            )
            self._build("win", interaction.user)
            try:
                await interaction.response.edit_message(
                    view=self,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                LOG.exception("Quiz won, but UI edit failed")
                if not interaction.response.is_done():
                    await fail(interaction, "Récompense créditée, mais affichage indisponible.")
            self.stop()

    async def on_timeout(self):
        async with self._lock:
            if self.finished:
                return
            self.finished = True
            self._build("timeout")
            if self.message:
                try:
                    await self.message.edit(
                        view=self,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.HTTPException,discord.NotFound):
                    LOG.warning("Quiz expired: original message unavailable")
            self.stop()


class QuizGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="quiz", description="🧩 Quiz à 4 réponses, catégories et difficultés"
    )
    @app_commands.guild_only()
    async def quiz(
        self,
        interaction: discord.Interaction,
        categorie: Literal["halloween", "horreur", "science", "culture"] = "halloween",
        difficulte: Literal["facile", "moyen", "difficile", "expert"] = "facile",
    ):
        guild_id, user_id = interaction.guild.id, interaction.user.id
        seconds = self.bot.store.cooldown(guild_id, user_id, "quiz_spawn", 120)
        if seconds:
            return await fail(interaction, wait_text(seconds))
        data = generate_question(categorie, difficulte)
        view = MultipleChoice(guild_id, data)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="film_horreur", description="🎬 Devine le film d'horreur d'après une image"
    )
    @app_commands.guild_only()
    async def film_horreur(
        self,
        interaction: discord.Interaction,
        difficulte: Literal["facile", "moyen", "difficile"] = "facile",
    ):
        guild_id, user_id = interaction.guild.id, interaction.user.id
        seconds = self.bot.store.cooldown(guild_id, user_id, "film_spawn", 180)
        if seconds:
            return await fail(interaction, wait_text(seconds))
        data = generate_film(difficulte)
        view = MultipleChoice(guild_id, data, film=True)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(QuizGames(bot))
