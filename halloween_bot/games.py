"""Halloween mini-games: ghost hunt, trick-or-treat, quizzes, duels, boss and expedition."""
from __future__ import annotations

import random
import time
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands

from .common import card, fail, wait_text, OwnerView, themed_view, progress
from .content import QUIZZES,RIDDLES,HUNTS


class QuizView(OwnerView):
    def __init__(self,owner_id,guild_id,answers,correct):
        super().__init__(owner_id,timeout=90)
        self.guild_id=guild_id
        self.correct=correct
        self.answers=answers
        self.finished=False
        self.message=None
        for index,answer in enumerate(answers):
            button=discord.ui.Button(label=f"{'ABC'[index]} · {answer[:70]}",style=discord.ButtonStyle.secondary)
            async def choose(interaction,i=index):
                if self.finished:
                    return await fail(interaction,"Cette énigme est déjà terminée.")
                self.finished=True
                for component in self.children:
                    component.disabled=True
                if i==self.correct:
                    interaction.client.store.award(self.guild_id,self.owner_id,85,quizzes=1)
                    desc="🎉 **Bonne réponse !**\n\n🍬 **+85 bonbons**."
                else:
                    desc=f"💀 Mauvaise réponse !\n\n🕯️ Réponse : **{self.answers[self.correct]}**."
                await interaction.response.edit_message(
                    embed=card("Le verdict des ombres", desc,
                               theme="success" if i == self.correct else "danger",
                               sections=[("🧩  RÉSULTAT",
                                          "Réponse validée." if i == self.correct else "Réessaie plus tard.",
                                          False)]),
                    view=self)
                self.stop()
            button.callback=choose
            self.add_item(button)

    async def on_timeout(self):
        self.finished=True
        for button in self.children:
            button.disabled=True
        if self.message:
            try:
                await self.message.edit(embed=card("ÉNIGME EXPIRÉE","🌫️ L'énigme s'est dissipée."),view=self)
            except discord.HTTPException:
                pass


from .adventure_games import (
    GhostHuntView, PumpkinView, ExpeditionView, DuelView, BossView, send_adventure,
)


class Games(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    @app_commands.command(name="trickortreat",description="🎃 Explore le manoir hanté et choisis une porte")
    @app_commands.guild_only()
    async def trickortreat(self,interaction:discord.Interaction):
        from .trick_or_treat import TrickOrTreatView
        if not interaction.app_permissions.attach_files:
            return await fail(interaction,"Autorise le bot à joindre des images pour afficher le manoir.")
        if interaction.user.bot:
            return await fail(interaction,"Cette aventure est réservée aux joueurs.")
        g,u=interaction.guild.id,interaction.user.id
        view=TrickOrTreatView(self.bot,g,u)
        # Public on every invocation (including during cooldown); only the
        # invoker controls this panel. Other members can run /trickortreat.
        await interaction.response.send_message(
            view=view,file=view._view_file(),
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        view.message=await interaction.original_response()

    @app_commands.command(name="ghosthunt",description="👻 Traquer un fantôme caché dans le cimetière")
    @app_commands.guild_only()
    async def ghosthunt(self,interaction:discord.Interaction):
        view=GhostHuntView(self.bot,interaction.guild.id,interaction.user.id)
        await send_adventure(interaction,view)

    @app_commands.command(name="pumpkin",description="🎃 Choisir et ouvrir une citrouille mystérieuse")
    @app_commands.guild_only()
    async def pumpkin(self,interaction:discord.Interaction):
        view=PumpkinView(self.bot,interaction.guild.id,interaction.user.id)
        await send_adventure(interaction,view)

    @app_commands.command(name="duel",description="⚔️ Défier un joueur au combat tour par tour")
    @app_commands.guild_only()
    async def duel(self,interaction:discord.Interaction,adversaire:discord.Member):
        if not interaction.app_permissions.attach_files:
            return await fail(interaction,"Autorise « Joindre des fichiers » pour lancer un duel.")
        if adversaire.bot or adversaire.id==interaction.user.id:
            return await fail(interaction,"Choisis un autre joueur humain.")
        guild_id,user_id=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(guild_id,user_id,"duel",300)
        if wait:return await fail(interaction,wait_text(wait))
        view=DuelView(self.bot,guild_id,user_id,adversaire.id,
                      (interaction.user.display_name,adversaire.display_name))
        await send_adventure(interaction,view,mention_user=adversaire)

    @app_commands.command(name="boss",description="💀 Combattre le Roi des Citrouilles ensemble")
    @app_commands.guild_only()
    async def boss(self,interaction:discord.Interaction):
        if not interaction.app_permissions.attach_files:
            return await fail(interaction,"Autorise « Joindre des fichiers » pour lancer le boss.")
        guild_id=interaction.guild.id
        if guild_id in self.bot.active_bosses:
            return await fail(interaction,"Un boss combat déjà sur le serveur.")
        wait=self.bot.store.cooldown(guild_id,0,"boss_global",1200)
        if wait:return await fail(interaction,wait_text(wait))
        view=BossView(self.bot,guild_id)
        self.bot.active_bosses[guild_id]=view
        try:
            await send_adventure(interaction,view)
        except Exception:
            self.bot.active_bosses.pop(guild_id,None)
            raise

    @app_commands.command(name="expedition",description="🏚️ Choisir ton chemin dans une expédition hantée")
    @app_commands.guild_only()
    async def expedition(self,interaction:discord.Interaction):
        view=ExpeditionView(self.bot,interaction.guild.id,interaction.user.id)
        await send_adventure(interaction,view)




async def setup(bot):
    await bot.add_cog(Games(bot))
