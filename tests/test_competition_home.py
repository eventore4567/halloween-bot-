"""Regression coverage for the completely styled /competition dashboard."""
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
    FILENAME, HEIGHT, URI, WIDTH, banner_bytes,
    discord_banner, competition_files,
)
from halloween_bot.ornaments import BADGES, SIZE, badge_bytes, badge_file
from halloween_bot.competition_store import Competition
from halloween_bot.round_store import RoundStore
from halloween_bot.storage import Store
from halloween_bot.visuals import CompetitionHome


def all_text(root):
    output = []
    if isinstance(root, discord.ui.TextDisplay):
        output.append(root.content)
    for child in getattr(root, "children", []):
        output.extend(all_text(child))
    return "\n".join(output)


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

    def test_banner_has_readable_original_panorama(self):
        data = banner_bytes()
        self.assertGreater(len(data), 12_000)
        self.assertLess(len(data), 5_000_000)
        picture = Image.open(io.BytesIO(data))
        self.assertEqual(picture.format, "JPEG")
        self.assertEqual(picture.size, (WIDTH, HEIGHT))
        self.assertNotEqual(picture.getpixel((20,20)), picture.getpixel((1200,90)))
        self.assertEqual(URI, f"attachment://{FILENAME}")

    def test_image_files_are_fresh_on_every_interaction(self):
        first = discord_banner()
        second = discord_banner()
        self.assertIsNot(first,second)
        self.assertEqual(first.filename,FILENAME)
        self.assertEqual(second.filename,FILENAME)
        self.assertIsNot(first.fp,second.fp)
        first.close()
        second.close()

    def test_three_matching_emblems_are_real_pngs(self):
        self.assertEqual(BADGES,("portal","rank","grimoire"))
        images=[]
        for name in BADGES:
            raw=badge_bytes(name)
            self.assertGreater(len(raw),1000)
            img=Image.open(io.BytesIO(raw))
            self.assertEqual(img.format,"PNG")
            self.assertEqual(img.size,(SIZE,SIZE))
            images.append(raw)
        self.assertEqual(len(set(images)),3)
        with self.assertRaises(ValueError):
            badge_bytes("unknown")

    def test_four_uploaded_files_and_no_external_image_urls(self):
        uploads=competition_files()
        try:
            self.assertEqual(len(uploads),4)
            self.assertEqual(
                [item.filename for item in uploads],
                ["crypt-cup-banner.jpg","crypt-portal.png",
                 "crypt-rank.png","crypt-grimoire.png"]
            )
            for item in uploads:
                self.assertTrue(item.fp.read(8))
                item.fp.seek(0)
        finally:
            for item in uploads:
                item.close()

    def test_one_container_with_three_true_illustrated_sections(self):
        view=self.make_view(self.bot,self.guild,self.player)
        self.assertEqual(len(view.children),1)
        panel=view.children[0]
        self.assertIsInstance(panel,discord.ui.Container)
        self.assertEqual(len(panel.children),10)
        self.assertEqual(
            sum(isinstance(c,discord.ui.MediaGallery) for c in panel.children),1
        )
        sections=[c for c in panel.children if isinstance(c,discord.ui.Section)]
        self.assertEqual(len(sections),3)
        for section in sections:
            self.assertIsInstance(section.accessory,discord.ui.Thumbnail)
            self.assertGreater(len(section.children),0)
        actions=[c for c in panel.children if isinstance(c,discord.ui.ActionRow)]
        self.assertEqual(len(actions),2)
        self.assertEqual(sum(len(row.children) for row in actions),5)
        self.assertEqual(
            [button.label for row in actions for button in row.children],
            ["Participer","Mes défis","Top 10","Mon rang","Règlement"],
        )
        # Accidental duplicate command boxes would show as multiple containers.
        self.assertTrue(all(not isinstance(c,discord.ui.Container)
                            for c in panel.children))

    def test_unconfigured_competition_still_renders_and_tells_why(self):
        view=self.make_view(self.bot,self.guild,self.player)
        description=all_text(view)
        self.assertIn("LE PORTAIL EST FERMÉ",description)
        self.assertIn("/setup",description)
        self.assertIn("TON BLASON DE CHASSEUR",description)
        self.assertIn("LE GRIMOIRE DES ÉPREUVES",description)

    def test_active_signups_show_real_deadline(self):
        now=int(time.time())
        self.competition.start(self.guild.id,self.player.id,
                               now+4*86400,now=now)
        self.round_store.configure(self.guild.id,channel_id=10,role_id=20)
        self.assertEqual(
            self.round_store.enable(self.guild.id,now=now),"enabled"
        )
        ids=self.round_store.claim_due(now=now)
        self.assertEqual(len(ids),1)
        view=self.make_view(self.bot,self.guild,self.player)
        description=all_text(view)
        self.assertIn("INSCRIPTIONS SONT OUVERTES",description)
        self.assertIn(str(self.round_store.round(ids[0])["signup_ends_at"]),
                      description)

    def test_rank_reflects_saved_competition_points(self):
        now=int(time.time())
        self.competition.start(self.guild.id,self.player.id,
                               now+4*86400,now=now)
        self.competition.join(self.guild.id,self.player.id,now=now+1)
        view=self.make_view(self.bot,self.guild,self.player)
        description=all_text(view)
        self.assertIn("**#1**",description)
        self.assertIn("**0 pts**",description)


if __name__=="__main__":
    unittest.main()
