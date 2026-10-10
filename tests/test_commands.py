"""Ensure every Discord slash command loads before any real Discord connection."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path


class CommandTests(unittest.TestCase):
    def test_all_modules_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_PATH"]=str(Path(tmp)/"discord-test.sqlite3")
            from main import HalloweenBot

            async def verify():
                bot=HalloweenBot()
                try:
                    for module in ("economy","games","farming","events","admin","competition","rounds","quiz_games"):
                        await bot.load_extension("halloween_bot."+module)
                    actual={command.name for command in bot.tree.get_commands()}
                    required={
                        "halloween","daily","trickortreat","ghosthunt",
                        "pumpkin","quiz","duel","boss","expedition",
                        "farm","leaderboard","profile","shop","inventory",
                        "give","achievements","guide","setup",
                        "competition","challenge","film_horreur"
                    }
                    self.assertTrue(required<=actual,required-actual)
                    self.assertEqual(len(actual),len(required))
                finally:
                    await bot.close()
            asyncio.run(verify())
            os.environ.pop("DATABASE_PATH",None)
