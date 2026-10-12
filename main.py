"""Nuit Hantée — Discord Halloween bot. Start with: python3 main.py

Secret required: ``discord_token`` (or ``DISCORD_TOKEN``).
Optional: ``DATA_DIR`` (persistent volume, e.g. /data), ``BOT_TIMEZONE``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

from halloween.art import banners
from halloween.content import quiz_bank
from halloween.db import Store
from halloween.emojis import sync_emojis
from halloween.ui import notice, register_navigation

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
LOG = logging.getLogger("nuit-hantee")

COGS = (
    "hub", "profile", "daily", "quiz", "expedition", "formula", "wheel", "memory", "hunt",
    "hangman", "duel", "cards", "shop", "leaderboard", "gift", "drops", "admin",
    "house", "race", "ritual", "reflex", "curse", "trophies", "seasonal", "ouija", "shell", "challenges", "slots", "motus", "hilo", "versus", "maze", "connect4", "pet", "roulette", "film", "escape", "reminder",
)


class NuitHantee(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()  # no privileged intent needed
        super().__init__(command_prefix=commands.when_mentioned, intents=intents,
                         allowed_mentions=discord.AllowedMentions.none(), help_command=None)
        data_dir = os.environ.get("DATA_DIR", "/data" if Path("/data").is_dir() else "data")
        db_path = os.getenv("DATABASE_PATH", str(Path(data_dir) / "nuit_hantee.sqlite3"))
        self.store = Store(db_path)
        self.openers = {}
        self._bg_tasks = set()

    async def setup_hook(self):
        for name in COGS:
            await self.load_extension(f"halloween.cogs.{name}")
        register_navigation(self)
        self.tree.on_error = self.on_app_command_error
        synced = await self.tree.sync()
        LOG.info("Synced %s slash commands", len(synced))
        self._spawn(sync_emojis(self, self.store))
        self._spawn(asyncio.to_thread(banners.prerender_all, questions=quiz_bank.TOTAL))

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def on_ready(self):
        LOG.info("Connected as %s (%s) on %s servers", self.user, self.user.id, len(self.guilds))
        await self.change_presence(activity=discord.Game(name="🎃 /jeux · Nuit Hantée"))

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        original = getattr(error, "original", error)
        if isinstance(error, discord.app_commands.CheckFailure):
            text = "Tu n'as pas la permission d'utiliser cette commande."
        elif isinstance(error, discord.app_commands.NoPrivateMessage):
            text = "Cette commande se joue dans un serveur."
        else:
            LOG.error("Slash command error", exc_info=original)
            text = "Un sortilège a mal tourné… réessaie dans un instant."
        try:
            await notice(interaction, text)
        except discord.HTTPException:
            pass

    async def close(self):
        await super().close()
        self.store.close()


def main():
    token = os.getenv("discord_token") or os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Variable d'environnement discord_token (ou DISCORD_TOKEN) manquante.")
    NuitHantee().run(token, log_handler=None)


if __name__ == "__main__":
    main()
