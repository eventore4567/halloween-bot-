"""CRYPT CUP arcade: seven small interactive Discord Components V2 games.

All games are reachable from a SINGLE slash command (/jeux) and an existing
/halloween hub button. Avoids command spam. Visuals use original in-app
Halloween art, native controls and custom application emojis. One player owns
each ephemeral session. A SQLite-backed per-mode cooldown prevents farming;
rewards are virtual candies only, never cash-prize competition points.
"""
from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from .common import button_icon, fail, wait_text
from .mini_art import FILENAME, banner_file
from .mini_engine import MODES, MiniSession, TTL_SECONDS

LOG = logging.getLogger(__name__)

INTRO = (
    "### 🕹️ LE CABINET DES JEUX\n"
    "Sept petites aventures à jouer seul, sans argent ni mise.\n"
    "Découvre la bonne porte, fabrique des potions, capture un fantôme ou "
    "affronte le démon. Les récompenses sont des **bonbons virtuels**.\n"
    "-# Aucun de ces jeux ne donne de points pour le concours CRYPT CUP."
)
COOLDOWN_SECONDS = 120
SKILL_MODES = frozenset(("memoire", "labyrinthe", "chaudron"))


def _gallery():
    return discord.ui.MediaGallery(
        discord.MediaGalleryItem(media=f"attachment://{FILENAME}")
    )


class ArcadeHub(discord.ui.LayoutView):
    """Seven launch buttons on two balanced rows, with no grey containers."""

    def __init__(self, bot, owner_id: int, guild_id: int):
        super().__init__(timeout=480)
        self.bot = bot
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.add_item(_gallery())
        self.add_item(discord.ui.TextDisplay(INTRO))

        buttons=[]
        for mode, (title, description, max_reward, emoji_key) in MODES.items():
            b=discord.ui.Button(
                label=title[:75], emoji=button_icon(emoji_key),
                style=(discord.ButtonStyle.primary
                       if mode in SKILL_MODES else
                       discord.ButtonStyle.secondary),
                custom_id=f"crypt:arcade:launch:{mode}",
            )

            async def click(interaction, chosen=mode):
                await self.launch(interaction,chosen)

            b.callback=click
            buttons.append(b)
        self.add_item(discord.ui.ActionRow(*buttons[:4]))
        self.add_item(discord.ui.ActionRow(*buttons[4:]))

    async def interaction_check(self, interaction: discord.Interaction):
        if (not interaction.guild or interaction.guild.id!=self.guild_id
                or interaction.user.id != self.owner_id
                or interaction.user.bot):
            await fail(interaction,"Ce cabinet des jeux appartient à un autre joueur.")
            return False
        return True

    async def launch(self,interaction,mode):
        if mode not in MODES:
            return await fail(interaction,"Jeu introuvable.")
        wait=self.bot.store.cooldown(
            self.guild_id,self.owner_id,"minigame:"+mode,COOLDOWN_SECONDS
        )
        if wait:
            return await fail(interaction,wait_text(wait))
        game=MiniGameView(self.bot,self.guild_id,self.owner_id,mode)
        try:
            await interaction.response.send_message(
                view=game,file=banner_file(mode),ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            LOG.exception("Unable to launch arcade game: %s",mode)
            raise
        game.message=await interaction.original_response()
        game.schedule_reveal()


class MiniGameView(discord.ui.LayoutView):
    def __init__(self,bot,guild_id:int,owner_id:int,mode:str):
        super().__init__(timeout=TTL_SECONDS + 3)
        self.bot=bot
        self.guild_id=guild_id
        self.owner_id=owner_id
        self.session=MiniSession(mode)
        self.message=None
        self._lock=asyncio.Lock()
        self._feedback=""
        self._last_selected=None
        self._draw()

    async def interaction_check(self,interaction:discord.Interaction):
        if (not interaction.guild or interaction.guild.id != self.guild_id
                or interaction.user.id != self.owner_id
                or interaction.user.bot):
            await fail(interaction,"Cette partie appartient à un autre joueur.")
            return False
        return True

    def _draw(self):
        self.clear_items()
        s=self.session
        title,description,max_reward,emoji_key=MODES[s.mode]
        remaining=int(time.time()+max(0,s.deadline-time.monotonic()))
        self.add_item(_gallery())
        if s.done:
            prize=(
                f"🍬 **+{self._earned} bonbons** ajoutés à ton inventaire."
                if getattr(self,"_earned",0)>0 else
                "🕸️ **Aucun bonbon gagné** pour cette tentative."
            )
            info=(
                f"### {'🏆 VICTOIRE !' if s.success else '🕯️ PARTIE TERMINÉE'}\n"
                f"{s.last}\n\n{prize}\n"
                "-# Tu peux lancer un autre jeu depuis /jeux."
            )
        else:
            info=(
                f"### {title.upper()}\n"
                f"{description}\n\n"
                f"{s.prompt()}\n\n"
                f"🍬 Gain possible : **jusqu'à {max_reward} bonbons** "
                f"• ⏳ Fin <t:{remaining}:R>\n"
            )
            if self._feedback:
                info+="\n"+self._feedback
        self.add_item(discord.ui.TextDisplay(info))
        buttons=[]
        for i,label in enumerate(s.options()):
            icon = (
                button_icon("ghost") if s.mode=="reflexe" else
                button_icon("key") if s.mode in ("labyrinthe","coffres","fantomes")
                else button_icon("book") if s.mode in ("memoire","chaudron")
                else button_icon("skull")
            )
            button=discord.ui.Button(
                label=label[:80],emoji=icon,
                style=(discord.ButtonStyle.success
                       if s.done and s.success and i==self._last_selected else
                       discord.ButtonStyle.secondary
                       if s.done else
                       discord.ButtonStyle.primary),
                custom_id=f"crypt:arcade:pick:{s.mode}:{i}",
                disabled=not s.available(),
            )

            async def handler(interaction,choice=i):
                await self.pick(interaction,choice)

            button.callback=handler
            buttons.append(button)
        self.add_item(discord.ui.ActionRow(*buttons))

    async def pick(self,interaction,choice):
        async with self._lock:
            result=self.session.choose(choice)
            if result.status in ("waiting","invalid","used"):
                return await fail(interaction,result.message)
            if result.status=="timeout":
                self._earned=0
                self._feedback=""
            elif result.status=="progress":
                self._feedback=f"✅ **Étape réussie !** {self.session.step} bonne(s) réponse(s)."
            else:
                self._feedback=""
                if result.status=="won":
                    # Strictly virtual economy. Never writes tournament tables.
                    self.bot.store.award(
                        self.guild_id,self.owner_id,result.reward,
                        **({"quizzes":1} if self.session.mode in SKILL_MODES else {})
                    )
                    self._earned=result.reward
                else:
                    self._earned=0
                self._last_selected=choice
            self._draw()
            try:
                await interaction.response.edit_message(
                    view=self, allowed_mentions=discord.AllowedMentions.none()
                )
            except discord.HTTPException:
                LOG.exception("Arcade answer processed, but view edit failed")
                if not interaction.response.is_done():
                    await fail(
                        interaction,
                        "Le résultat a été enregistré, mais l'affichage a échoué.",
                    )
            if self.session.done:
                self.stop()

    def schedule_reveal(self):
        if self.session.mode not in ("memoire","reflexe"):
            return
        asyncio.create_task(self._reveal())

    async def _reveal(self):
        await asyncio.sleep(max(0,self.session.ready_at-time.monotonic()))
        async with self._lock:
            if self.session.done or self.message is None:
                return
            self._draw()
            try:
                await self.message.edit(
                    view=self,allowed_mentions=discord.AllowedMentions.none()
                )
            except (discord.HTTPException,discord.NotFound):
                LOG.warning("Cannot unlock minigame %s",self.session.mode)

    async def on_timeout(self):
        async with self._lock:
            if self.session.done:
                return
            self.session.expire()
            self._earned=0
            self._draw()
            if self.message:
                try:
                    await self.message.edit(
                        view=self,allowed_mentions=discord.AllowedMentions.none()
                    )
                except (discord.HTTPException,discord.NotFound):
                    LOG.warning("Expired minigame message not available")
            self.stop()


class MiniArcade(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    async def send_hub(self,interaction:discord.Interaction):
        if not interaction.guild:
            return await fail(interaction,"Les jeux sont disponibles sur un serveur.")
        await interaction.response.send_message(
            view=ArcadeHub(self.bot,interaction.user.id,interaction.guild.id),
            file=banner_file("menu"),ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="jeux",
        description="🎃 Sept mini-jeux Halloween dans le cabinet des ombres",
    )
    @app_commands.guild_only()
    async def jeux(self,interaction:discord.Interaction):
        await self.send_hub(interaction)


async def setup(bot):
    await bot.add_cog(MiniArcade(bot))
