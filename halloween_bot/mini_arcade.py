"""CRYPT CUP arcade: seven small interactive Discord Components V2 games.

All seven games have their own slash command (/memoire, /reflexe,
/labyrinthe, /chaudron, /coffres, /des, /fantomes) in addition to the /jeux
and /halloween menus. A shared launcher gives both entry points identical
cooldowns, owner checks, images, buttons and rewards.
Each public session belongs to one player; rewards are virtual candy only,
never cash-prize competition points.
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
from .mini_scene import FILENAME as GAME_FILENAME, game_file
from .mini_engine import MODES, MiniSession, TTL_SECONDS

LOG = logging.getLogger(__name__)

INTRO = (
    "### 🕹️ LE CABINET DES JEUX\n"
    "Sept jeux disponibles directement avec leurs propres commandes /, "
    "ou depuis ce catalogue.\n"
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


def _game_gallery():
    return discord.ui.MediaGallery(
        discord.MediaGalleryItem(media=f"attachment://{GAME_FILENAME}")
    )


async def launch_mini_game(bot, interaction: discord.Interaction, mode: str):
    """Canonical launcher for BOTH the /jeux catalogue and direct slash commands.

    All seven modes use the same cooldown key and one-shot payout regardless
    of entry point. Never consume a cooldown on a server with no attachment
    permission, where the game cannot be shown.
    """
    if mode not in MODES:
        return await fail(interaction, "Jeu introuvable.")
    if not interaction.guild:
        return await fail(interaction, "Les mini-jeux sont réservés aux serveurs.")
    if not getattr(interaction.app_permissions, "attach_files", False):
        return await fail(interaction, "Autorise « Joindre des fichiers » pour jouer.")

    guild_id=interaction.guild.id
    user_id=interaction.user.id
    wait=bot.store.cooldown(
        guild_id, user_id, "minigame:"+mode, COOLDOWN_SECONDS
    )
    if wait:
        return await fail(interaction, wait_text(wait))
    game=MiniGameView(bot,guild_id,user_id,mode)
    try:
        await interaction.response.send_message(
            view=game, file=game.art(), ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        LOG.exception("Unable to launch arcade game: %s", mode)
        raise
    game.message=await interaction.original_response()
    game.schedule_reveal()


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
        await launch_mini_game(self.bot,interaction,mode)


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

    def art(self):
        """Render current game state, not a static intro reused at every step."""
        return game_file(self.session,earned=getattr(self,"_earned",0))

    def _draw(self):
        self.clear_items()
        s=self.session
        self.add_item(_game_gallery())
        if s.done:
            # The final art already contains the result and reward; leaving
            # inert buttons under it was misleading.
            return
        buttons=[]
        for index,label in enumerate(s.options()):
            icon = (
                button_icon("ghost") if s.mode=="reflexe" else
                button_icon("key") if s.mode in ("labyrinthe","coffres","fantomes")
                else button_icon("book") if s.mode in ("memoire","chaudron")
                else button_icon("skull")
            )
            button=discord.ui.Button(
                label=label[:80],emoji=icon,
                style=discord.ButtonStyle.primary,
                custom_id=f"crypt:arcade:pick:{s.mode}:{index}",
                disabled=not s.available(),
            )
            async def handler(interaction,choice=index):
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
                    view=self, attachments=[self.art()],
                    allowed_mentions=discord.AllowedMentions.none()
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
                    view=self,attachments=[self.art()],
                    allowed_mentions=discord.AllowedMentions.none()
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
                        view=self,attachments=[self.art()],
                        allowed_mentions=discord.AllowedMentions.none()
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
            file=banner_file("menu"),ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="jeux",
        description="🎃 Sept mini-jeux Halloween dans le cabinet des ombres",
    )
    @app_commands.guild_only()
    async def jeux(self,interaction:discord.Interaction):
        await self.send_hub(interaction)


    @app_commands.command(
        name="memoire", description="🔮 Mémoire des runes : retrouve 4 symboles dans l'ordre"
    )
    @app_commands.guild_only()
    async def memoire(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"memoire")

    @app_commands.command(
        name="reflexe", description="👻 Réflexe du fantôme : attrape-le au bon moment"
    )
    @app_commands.guild_only()
    async def reflexe(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"reflexe")

    @app_commands.command(
        name="labyrinthe", description="🚪 Labyrinthe maudit : franchis trois portes"
    )
    @app_commands.guild_only()
    async def labyrinthe(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"labyrinthe")

    @app_commands.command(
        name="chaudron", description="🧪 Chaudron magique : prépare les bonnes potions"
    )
    @app_commands.guild_only()
    async def chaudron(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"chaudron")

    @app_commands.command(
        name="coffres", description="🎁 Coffres hantés : découvre ton trésor"
    )
    @app_commands.guild_only()
    async def coffres(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"coffres")

    @app_commands.command(
        name="des", description="🎲 Dés du démon : prédis son prochain lancer"
    )
    @app_commands.guild_only()
    async def des(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"des")

    @app_commands.command(
        name="fantomes", description="🪦 Chasse spectrale : choisis la tombe secrète"
    )
    @app_commands.guild_only()
    async def fantomes(self,interaction:discord.Interaction):
        await launch_mini_game(self.bot,interaction,"fantomes")



async def setup(bot):
    await bot.add_cog(MiniArcade(bot))
