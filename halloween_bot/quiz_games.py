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
from .mini_art import banner_file, FILENAME
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
        """Flat arcade layout: no two heavy grey containers, no ALT tag."""
        self.clear_items()
        data=self.data
        difficulty=DIFFICULTIES[data["difficulty"]]["label"]
        name="🎬 LE CINÉMA HANTÉ" if self.film else "🧩 LE QUIZ DES TÉNÈBRES"
        hero = data["image"] if self.film else f"attachment://{FILENAME}"
        self.add_item(discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=hero)
        ))
        state=(
            f"🏆 **Bonne réponse de {winner.display_name} !**"
            if outcome=="win" and winner else
            "⌛ **TEMPS ÉCOULÉ — FIN DU QUIZ**"
            if outcome=="timeout" else
            "Choisis la bonne réponse avant les autres chasseurs."
        )
        text=(
            f"-# ✧ HALLOWEEN • CRYPT CUP\n"
            f"### {name}\n"
            f"**{pretty(data['question'])}**\n\n"
            f"🎯 **{difficulty}**  ·  🍬 **{data['reward']} bonbons**\n"
            f"⏳ {'Terminé' if outcome else f'<t:{self.deadline}:R>'}\n"
            f"{state}"
        )
        if outcome:
            answer_index=data["correct"]
            text+=(
                f"\n\n### ✅ LA RÉPONSE\n"
                f"**{'ABCD'[answer_index]}. {pretty(data['answers'][answer_index])}**"
            )
            if outcome=="win" and winner:
                text+=f"\n🍬 **+{data['reward']} bonbons** distribués."
            if self.film:
                text+=(
                    f"\n-# Film de {data['year']} • "
                    f"[Source Wikimedia Commons]({data['source']})"
                )
        else:
            text+="\n-# Une seule proposition par joueur."
        self.add_item(discord.ui.TextDisplay(text))
        answers=[]
        for i,option in enumerate(data["answers"]):
            is_correct=outcome is not None and i==data["correct"]
            button=discord.ui.Button(
                label=f"{'ABCD'[i]} • {option}"[:80],
                style=(
                    discord.ButtonStyle.success if is_correct
                    else discord.ButtonStyle.secondary if outcome
                    else discord.ButtonStyle.primary
                ),
                custom_id=f"crypt:quiz:{'ABCD'[i]}:{self.deadline}",
                disabled=bool(outcome),
            )

            async def handler(interaction, selection=i):
                await self.choose(interaction,selection)

            button.callback=handler
            answers.append(button)
        self.add_item(discord.ui.ActionRow(*answers[:2]))
        self.add_item(discord.ui.ActionRow(*answers[2:]))

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

    async def absolute_timeout(self):
        """Reveal the answer at the exact deadline, even during heavy activity."""
        await asyncio.sleep(max(0, self.deadline - time.time()))
        await self.on_timeout()

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
        await interaction.response.send_message(
            view=view, file=banner_file("quiz"),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        view.message = await interaction.original_response()
        asyncio.create_task(view.absolute_timeout())

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
        asyncio.create_task(view.absolute_timeout())


async def setup(bot):
    await bot.add_cog(QuizGames(bot))
