"""/film — « Le Film de ta Nuit »: a personal animated movie made from your season, posted for everyone."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art.film import film_gif
from ..content import pet as P
from ..content.games import CARDS
from ..emojis import E
from ..ui import Panel, image_file, nav, notice, relative
from .profile import avatar_bytes

FILE = "film.gif"
COOLDOWN = 10 * 60


def best_moment(stats: dict) -> str:
    """The most impressive thing this player did, for the scene without a pet."""
    options = [
        (stats.get("slots_jackpot", 0) * 100, "Jackpot à la Machine hantée"),
        (stats.get("show_top", 0) * 90, "Les 12 marches du Grand Frisson"),
        (stats.get("show_best", 0) * 6, f"{stats.get('show_best', 0)} marches au Grand Frisson"),
        (stats.get("crypt", 0) * 40, "Le trésor de la crypte"),
        (stats.get("duel_win", 0) * 8, f"{stats.get('duel_win', 0)} duels gagnés"),
        (stats.get("maze_escape", 0) * 10, f"{stats.get('maze_escape', 0)} évasions du labyrinthe"),
        (stats.get("hunt_best", 0) // 10, f"Un pot de {stats.get('hunt_best', 0)} à la chasse"),
    ]
    score, text = max(options)
    return text if score > 0 else "Le début d'une légende"


def film_info(store, guild_id: int, member, avatar: bytes | None) -> dict:
    p = store.player(guild_id, member.id)
    stats = store.stats(guild_id, member.id)
    level = config.level_from_xp(p["xp"])[0]
    rank, players = store.rank(guild_id, member.id, "earned")
    owned = store.owned(guild_id, member.id)
    info = dict(name=member.display_name, avatar=avatar, title=config.rank_title(level), level=level,
                earned=p["earned"], quiz_right=stats.get("quiz_right", 0), cards=len(store.cards(guild_id, member.id)),
                cards_total=len(CARDS), achievements=sum(1 for t in owned if t.startswith("ach:")),
                achievements_total=len(config.ACHIEVEMENTS), rank=rank, players=max(players, 1),
                best=best_moment(stats), pet=None)
    pet = store.meta_get(f"pet:{guild_id}:{member.id}")
    if pet:
        sp = P.SPECIES[pet["species"]]
        info["pet"] = dict(name=pet["name"], icon=sp["icon"], color=sp["color"], stage=P.stage(pet["level"])[1],
                           level=pet["level"])
    return info


class Film(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["film"] = self.open

    async def open(self, interaction, edit=False, membre=None):
        member = membre or interaction.user
        store = self.bot.store
        left = store.cooldown_left(interaction.guild_id, interaction.user.id, "film")
        if left:
            return await notice(interaction, f"La salle de projection se prépare… reviens {relative(time.time() + left)}.",
                                icon="hourglass", color="purple")
        store.set_cooldown(interaction.guild_id, interaction.user.id, "film", COOLDOWN)
        await interaction.response.defer()
        avatar = await avatar_bytes(member)
        info = film_info(store, interaction.guild_id, member, avatar)
        data, seconds = await asyncio.to_thread(film_gif, info, random.randrange(1000))
        view = discord.ui.LayoutView(timeout=None)
        p = Panel("purple")
        p.title(f"Le Film de la Nuit de {member.display_name}", icon="eye",
                body=f"{E.sparkle} Une projection exclusive : sa saison d'Halloween en {round(seconds)} secondes. "
                     f"{E.candy} **{config.fmt(info['earned'])}** bonbons gagnés.")
        p.image(FILE)
        p.text(f"-# {E.lightning} Toi aussi, lance `/film` pour obtenir le tien !")
        p.row(nav("profile", interaction.user.id, "Mon profil", "pumpkin_lit"), nav("hub", interaction.user.id, "Jouer", "pumpkin"))
        view.add_item(p.container())
        await interaction.followup.send(view=view, files=[image_file(data, FILE)])

    @app_commands.command(name="film", description="🎬 Le Film de ta Nuit : ta saison d'Halloween en film animé")
    @app_commands.describe(membre="Le film de quelqu'un d'autre (par défaut : le tien)")
    @app_commands.guild_only()
    async def film(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        await self.open(interaction, membre=membre)


async def setup(bot):
    await bot.add_cog(Film(bot))
