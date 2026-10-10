"""Interactive community quiz and classic horror-film recognition.

Four Discord buttons; the first correct answer wins virtual bonbons. Wrong
answers are one-per-user. Timeouts show the correct option, as in the reference
screenshot. Film screenshots are sourced from public Commons file pages.
Neither game awards the real-prize tournament's skill points.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .common import card, fail, themed_view, wait_text
from .quiz_content import DIFFICULTIES, generate_question, generate_film

LOG = logging.getLogger(__name__)


class MultipleChoice(discord.ui.View):
    def __init__(self, guild_id, data, *, film=False):
        super().__init__(timeout=data["time"])
        self.guild_id = guild_id
        self.data = data
        self.film = film
        self.finished = False
        self.message = None
        self.attempted = set()
        self.lock = asyncio.Lock()
        self.deadline = int(time.time()) + data["time"]

        for i, choice in enumerate(data["answers"]):
            letter = "ABCD"[i]
            button = discord.ui.Button(
                label=f"{letter}  {choice}"[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"halloween:quiz:{letter}:{self.deadline}",
                row=0,
            )

            async def choose(interaction, selected=i):
                await self.choose(interaction, selected)

            button.callback = choose
            self.add_item(button)
        themed_view(self)

    def panel(self, result=None, winner=None):
        data = self.data
        title = (
            "Devine le film d'horreur" if self.film
            else "Le quiz des ténèbres"
        )
        difficulty = DIFFICULTIES[data["difficulty"]]["label"]
        if result == "timeout":
            description = "⌛ **Temps écoulé !** La porte du grimoire est fermée."
            theme = "danger"
        elif result == "win":
            description = f"🎉 **Bonne réponse de {winner.mention} !**"
            theme = "success"
        else:
            description = "🦇 **Une question, quatre réponses.** Sois le premier à trouver !"
            theme = "night"
        sections = [
            ("🧩  QUESTION", f"**{data['question']}**", False),
            ("🎯  DIFFICULTÉ", difficulty, True),
            ("🍬  RÉCOMPENSE", f"**{data['reward']} bonbons**", True),
            ("⏳  LIMITE", f"<t:{self.deadline}:R>", False),
        ]
        if result is not None:
            sections.append((
                "✅  BONNE RÉPONSE",
                f"**{'ABCD'[data['correct']]}. {data['answers'][data['correct']]}**",
                False,
            ))
            if self.film:
                sections.append((
                    "🎬  LE FILM",
                    f"Sorti en **{data['year']}** • "
                    f"[Source de l'image (Wikimedia Commons)]({data['source']})",
                    False,
                ))
        out = card(title, description, theme=theme, sections=sections)
        if self.film:
            out.set_image(url=data["image"])
            out.set_footer(text="🎬 Illustration issue de Wikimedia Commons • Bonbons virtuels")
        return out

    def mark_answers(self):
        correct = self.data["correct"]
        for i, button in enumerate(self.children):
            button.disabled = True
            if i == correct:
                button.style = discord.ButtonStyle.success
            else:
                button.style = discord.ButtonStyle.danger if i in self.attempted else discord.ButtonStyle.secondary

    async def choose(self, interaction, selected):
        if not interaction.guild or interaction.guild.id != self.guild_id:
            return await fail(interaction, "Ce quiz appartient à un autre serveur.")
        if interaction.user.bot:
            return await fail(interaction, "Seuls les membres peuvent participer.")
        async with self.lock:
            if self.finished or int(time.time()) >= self.deadline:
                return await fail(interaction, "Le quiz est déjà terminé.")
            if interaction.user.id in self.attempted:
                return await fail(interaction, "Une seule réponse par joueur !")
            self.attempted.add(interaction.user.id)
            if selected != self.data["correct"]:
                return await fail(interaction, "Mauvaise réponse ! Tu ne peux pas réessayer.")
            self.finished = True
            interaction.client.store.award(
                self.guild_id, interaction.user.id, self.data["reward"],
                quizzes=1,
            )
            self.mark_answers()
            try:
                await interaction.response.edit_message(
                    embed=self.panel("win", interaction.user),
                    view=self,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                LOG.exception("Failed to update completed quiz")
                if not interaction.response.is_done():
                    await fail(interaction, "Le quiz a été validé, mais l'affichage a échoué.")
            self.stop()

    async def on_timeout(self):
        async with self.lock:
            if self.finished:
                return
            self.finished = True
            self.mark_answers()
            if self.message:
                try:
                    await self.message.edit(
                        embed=self.panel("timeout"), view=self,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.HTTPException, discord.NotFound):
                    LOG.warning("Quiz message no longer available")
            self.stop()


class QuizGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="quiz", description="🧩 Quiz Halloween interactif : 4 catégories, 4 difficultés"
    )
    @app_commands.guild_only()
    async def quiz(
        self,
        interaction: discord.Interaction,
        categorie: Literal["halloween", "horreur", "science", "culture"] = "halloween",
        difficulte: Literal["facile", "moyen", "difficile", "expert"] = "facile",
    ):
        g, u = interaction.guild.id, interaction.user.id
        wait = self.bot.store.cooldown(g, u, "quiz_spawn", 120)
        if wait:
            return await fail(interaction, wait_text(wait))
        data = generate_question(categorie, difficulte)
        view = MultipleChoice(g, data)
        await interaction.response.send_message(embed=view.panel(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="film_horreur", description="🎬 Devine le film d'horreur grâce à une image"
    )
    @app_commands.guild_only()
    async def film_horreur(
        self,
        interaction: discord.Interaction,
        difficulte: Literal["facile", "moyen", "difficile"] = "facile",
    ):
        g, u = interaction.guild.id, interaction.user.id
        wait = self.bot.store.cooldown(g, u, "film_spawn", 180)
        if wait:
            return await fail(interaction, wait_text(wait))
        data = generate_film(difficulte)
        view = MultipleChoice(g, data, film=True)
        await interaction.response.send_message(embed=view.panel(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(QuizGames(bot))
