"""Regression coverage for the first rebuilt Halloween slash command: /competition."""
from __future__ import annotations

import asyncio
import io
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord
from PIL import Image

from halloween_bot.banner import (
    FILENAME, HEIGHT, URI, WIDTH, banner_bytes, discord_banner,
)
from halloween_bot.competition_store import Competition
from halloween_bot.round_store import RoundStore
from halloween_bot.storage import Store
from halloween_bot.visuals import CompetitionHome


class CompetitionHomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "main.sqlite3"))
        self.competition = Competition(self.store)
        self.round_store = RoundStore(self.store)
        self.bot = SimpleNamespace(
            store=self.store,
            competition=self.competition,
            round_store=self.round_store,
        )
        self.guild = SimpleNamespace(id=12345)
        self.player = SimpleNamespace(id=67890)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    @staticmethod
    def make_view(bot, guild, player):
        async def build():
            return CompetitionHome(bot, guild, player)
        return asyncio.run(build())

    def test_banner_is_original_png_free_attached_jpeg(self):
        data = banner_bytes()
        self.assertGreater(len(data), 12_000)
        self.assertLess(len(data), 5_000_000)
        picture = Image.open(io.BytesIO(data))
        self.assertEqual(picture.format, "JPEG")
        self.assertEqual(picture.size, (WIDTH, HEIGHT))
        self.assertNotEqual(picture.getpixel((20,20)), picture.getpixel((1200,90)))
        self.assertEqual(URI, f"attachment://{FILENAME}")

    def test_banner_file_can_be_reopened_per_interaction(self):
        first = discord_banner()
        second = discord_banner()
        self.assertIsNot(first, second)
        self.assertEqual(first.filename, FILENAME)
        self.assertEqual(second.filename, FILENAME)
        self.assertIsNot(first.fp, second.fp)
        first.close()
        second.close()

    def test_one_container_and_only_one(self):
        view = self.make_view(self.bot, self.guild, self.player)
        self.assertEqual(len(view.children), 1)
        main = view.children[0]
        self.assertIsInstance(main, discord.ui.Container)
        self.assertLessEqual(len(main.children), 10)
        gallery = [child for child in main.children
                   if isinstance(child, discord.ui.MediaGallery)]
        self.assertEqual(len(gallery), 1)
        actions = [child for child in main.children
                   if isinstance(child, discord.ui.ActionRow)]
        self.assertEqual(len(actions), 2)
        self.assertEqual(sum(len(row.children) for row in actions), 5)
        self.assertEqual(
            [button.label for row in actions for button in row.children],
            ["Participer", "Mes défis", "Top 10", "Mon rang", "Règlement"],
        )

    def test_unconfigured_competition_still_renders(self):
        view = self.make_view(self.bot, self.guild, self.player)
        description = " ".join(
            getattr(child, "content", "")
            for child in view.children[0].children
        )
        self.assertIn("PORTAIL EST FERMÉ", description)
        self.assertIn("Non classé", description)
        self.assertIn("/setup", description)

    def test_active_signups_show_real_deadline(self):
        now = int(time.time())
        self.competition.start(self.guild.id, self.player.id,
                               now + 4*86400, now=now)
        self.round_store.configure(self.guild.id, channel_id=10, role_id=20)
        self.assertEqual(
            self.round_store.enable(self.guild.id, now=now),
            "enabled",
        )
        ids = self.round_store.claim_due(now=now)
        self.assertEqual(len(ids), 1)
        view = self.make_view(self.bot, self.guild, self.player)
        description = " ".join(
            getattr(child, "content", "")
            for child in view.children[0].children
        )
        self.assertIn("INSCRIPTIONS OUVERTES", description)
        self.assertIn(
            str(self.round_store.round(ids[0])["signup_ends_at"]),
            description,
        )

    def test_rank_reflects_saved_competition_points(self):
        now = int(time.time())
        self.competition.start(self.guild.id, self.player.id,
                               now+4*86400, now=now)
        self.competition.join(self.guild.id,self.player.id,now=now+1)
        view = self.make_view(self.bot, self.guild, self.player)
        description = " ".join(
            getattr(child, "content", "")
            for child in view.children[0].children
        )
        self.assertIn("**#1**", description)
        self.assertIn("**0 point**", description)


if __name__ == "__main__":
    unittest.main()
