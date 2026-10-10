"""Run Halloween Bot with: python3 main.py. Secret: discord_token."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from halloween_bot.storage import Store
from halloween_bot.competition_store import Competition
from halloween_bot.round_store import RoundStore
from halloween_bot.common import ensure_application_emojis

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
LOG=logging.getLogger("halloween")


class HalloweenBot(commands.Bot):
    def __init__(self):
        intents=discord.Intents.default()
        super().__init__(command_prefix="!",intents=intents,
                         allowed_mentions=discord.AllowedMentions(
                             everyone=False,roles=False,users=True))
        data_dir=os.environ.get("DATA_DIR","/data" if Path("/data").is_dir() else "data")
        db_path=os.getenv("DATABASE_PATH",str(Path(data_dir)/"halloween.sqlite3"))
        self.store=Store(db_path)
        self.competition=Competition(self.store)
        self.round_store=RoundStore(self.store)
        self.active_bosses={}

    async def setup_hook(self):
        await ensure_application_emojis(self)
        for module in ("economy","games","farming","events","admin","competition","rounds","quiz_games"):
            await self.load_extension(f"halloween_bot.{module}")
        self.get_cog("Events").restore()
        self.get_cog("Rounds").restore()
        self.tree.on_error=self.command_error
        commands_synced=await self.tree.sync()
        LOG.info("🎃 Synced %s slash commands",len(commands_synced))

    async def on_ready(self):
        LOG.info("🎃 Connected as %s (%s)",self.user,self.user.id)
        await self.change_presence(
            activity=discord.Game(name="🏆 Halloween Cup • /competition"))

    async def command_error(self,interaction,error):
        LOG.error("Slash command error",exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "💀 Une erreur est survenue. Réessaie dans un instant.",
                    ephemeral=True)
            else:
                await interaction.response.send_message(
                    "💀 Une erreur est survenue. Réessaie dans un instant.",
                    ephemeral=True)
        except discord.HTTPException:
            pass

    async def close(self):
        await super().close()
        self.store.close()


def main():
    token=os.getenv("discord_token") or os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Variable discord_token manquante sur Railway.")
    bot=HalloweenBot()
    bot.run(token,log_handler=None)


if __name__=="__main__":
    main()
