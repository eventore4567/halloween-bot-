"""/classement — server leaderboards with a generated podium."""
from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import cards as art
from ..emojis import E
from ..ui import GameView, Panel, image_file, nav

BOARDS = {
    "candies": dict(name="Bonbons en poche", emoji="candy", unit="bonbons", fmt=config.fmt),
    "earned": dict(name="Bonbons gagnés", emoji="candy_bag", unit="gagnés", fmt=config.fmt),
    "xp": dict(name="Niveau", emoji="star", unit="", fmt=None),
    "quiz": dict(name="Maîtres du quiz", emoji="crystal", unit="bonnes réponses", fmt=config.fmt),
    "show": dict(name="Record du Grand Frisson", emoji="skull", unit="marches", fmt=str),
    "expedition": dict(name="Chefs d'expédition", emoji="key", unit="missions", fmt=config.fmt),
    "cards": dict(name="Collectionneurs", emoji="gift", unit="cartes", fmt=str),
    "duel": dict(name="Duellistes", emoji="vampire", unit="victoires", fmt=config.fmt),
}

_cache: dict[int, tuple[float, str, bytes | None]] = {}


async def who(bot, guild: discord.Guild | None, uid: int, with_avatar=False):
    hit = _cache.get(uid)
    if hit and time.time() - hit[0] < 600 and (hit[2] is not None or not with_avatar):
        return hit[1], hit[2]
    user = guild.get_member(uid) if guild else None
    try:
        if user is None and guild:
            user = await guild.fetch_member(uid)
    except discord.HTTPException:
        user = None
    if user is None:
        try:
            user = await bot.fetch_user(uid)
        except discord.HTTPException:
            return "Fantôme inconnu", None
    avatar = None
    if with_avatar:
        try:
            avatar = await user.display_avatar.replace(size=256, static_format="png").read()
        except (discord.HTTPException, ValueError):
            avatar = None
    _cache[uid] = (time.time(), user.display_name, avatar)
    return user.display_name, avatar


def value_text(kind, v):
    b = BOARDS[kind]
    if kind == "xp":
        lvl, _, _ = config.level_from_xp(v)
        return f"niveau {lvl}"
    return f"{b['fmt'](v)} {b['unit']}".strip()


class TopView(GameView):
    kicker = "LE PANTHÉON"
    owner_hint = "Ouvre ton propre classement avec /classement."

    def __init__(self, bot, interaction, kind="candies"):
        super().__init__(bot, interaction, timeout=600)
        self.kind = kind

    async def extra_files(self):
        rows = self.store.board(self.guild_id, self.kind, 3)
        guild = self.bot.get_guild(self.guild_id)
        entries = []
        found = await asyncio.gather(*(who(self.bot, guild, uid, True) for uid, _ in rows))
        for (uid, v), (name, avatar) in zip(rows, found):
            entries.append((name, value_text(self.kind, v), avatar))
        data = await asyncio.to_thread(art.podium, entries, f"Le Panthéon · {BOARDS[self.kind]['name']}")
        return [image_file(data, "podium.png")]

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        b = BOARDS[self.kind]
        p = Panel("gold").image("podium.png")
        rows = self.store.board(g, self.kind, 10)
        medals = [E.medal1, E.medal2, E.medal3]
        lines = []
        for i, (uid, v) in enumerate(rows):
            badge = medals[i] if i < 3 else f"`#{i + 1}`"
            me = " ← **toi**" if uid == u else ""
            lines.append(f"{badge} <@{uid}> · **{value_text(self.kind, v)}**{me}")
        rank, total = self.store.rank(g, u, self.kind)
        p.title(b["name"], icon=b["emoji"],
                body="\n".join(lines) if lines else "Personne n'est encore classé… sois le premier !")
        p.sep()
        if rank:
            p.text(f"{E.trophy} Ta place : **{rank}{'er' if rank == 1 else 'e'}** sur {total} joueurs")
        else:
            p.text(f"{E.trophy} Tu n'es pas encore classé ici. Joue pour entrer dans le Panthéon !")
        sel = discord.ui.Select(placeholder="Changer de classement…", options=[
            discord.SelectOption(label=v["name"], value=k, emoji=E.partial(v["emoji"]), default=k == self.kind)
            for k, v in BOARDS.items()])
        sel.callback = self._switch
        p.row(sel)
        p.row(nav("profile", self.owner_id, "Mon profil", "pumpkin_lit"), nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _switch(self, interaction):
        self.kind = interaction.data["values"][0]
        await interaction.response.defer()
        files = await self.extra_files()
        await self.refresh(interaction, attachments=files)


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["top"] = self.open
        bot.openers["top_exp"] = lambda interaction, edit=False: self.open(interaction, edit, kind="expedition")

    async def open(self, interaction, edit=False, kind="candies"):
        await interaction.response.defer(thinking=not edit)
        await TopView(self.bot, interaction, kind).start(interaction, edit)

    @app_commands.command(name="classement", description="🏆 Le Panthéon : les meilleurs joueurs du serveur")
    @app_commands.describe(type="Quel classement afficher ?")
    @app_commands.choices(type=[app_commands.Choice(name=v["name"], value=k) for k, v in BOARDS.items()])
    @app_commands.guild_only()
    async def classement(self, interaction: discord.Interaction, type: app_commands.Choice[str] | None = None):
        await self.open(interaction, kind=type.value if type else "candies")


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
