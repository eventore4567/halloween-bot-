"""The whole /competition UI must be one illustrated scene and real buttons."""
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

from halloween_bot.scene import (
    WIDTH, HEIGHT, SCENE_FILE, SCENE_URI,
    build_scene, competition_scene_file,
)
from halloween_bot.emoji_art import EMOJI_NAMES, render_emoji, SIZE
from halloween_bot.common import ICONS, ensure_application_emojis
from halloween_bot.competition_store import Competition
from halloween_bot.round_store import RoundStore
from halloween_bot.storage import Store
from halloween_bot.visuals import CompetitionHome


class CompetitionSceneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.temp.name)/"main.sqlite3"))
        self.competition=Competition(self.store)
        self.round_store=RoundStore(self.store)
        self.bot=SimpleNamespace(
            store=self.store,
            competition=self.competition,
            round_store=self.round_store,
        )
        self.guild=SimpleNamespace(id=12345)
        self.player=SimpleNamespace(id=67890)
        ICONS.install([])

    def tearDown(self):
        ICONS.install([])
        self.store.close()
        self.temp.cleanup()

    @staticmethod
    def make_view(bot,guild,player):
        async def build():
            return CompetitionHome(bot,guild,player)
        return asyncio.run(build())

    def test_full_scene_is_one_tall_jpeg_with_real_art(self):
        art=build_scene(self.bot,self.guild,self.player)
        self.assertGreater(len(art),40000)
        self.assertLess(len(art),8000000)
        image=Image.open(io.BytesIO(art))
        self.assertEqual(image.format,"JPEG")
        self.assertEqual(image.size,(WIDTH,HEIGHT))
        self.assertLessEqual(HEIGHT,900)
        self.assertGreaterEqual(WIDTH,1200)
        self.assertGreater(WIDTH,HEIGHT)
        self.assertGreaterEqual(WIDTH/HEIGHT,1.45)
        self.assertNotEqual(image.getpixel((140,140)),
                            image.getpixel((900,1200)))
        self.assertEqual(SCENE_URI,"attachment://"+SCENE_FILE)

    def test_different_competition_states_change_the_image(self):
        now=int(time.time())
        initial=build_scene(self.bot,self.guild,self.player,now=now)
        result=self.competition.start(
            self.guild.id,self.player.id,now+5*86400,now=now)
        self.assertEqual(result["status"],"started")
        other=build_scene(self.bot,self.guild,self.player,now=now)
        self.assertNotEqual(initial,other)
        self.competition.join(self.guild.id,self.player.id,now=now+1)
        ranked=build_scene(self.bot,self.guild,self.player,now=now+2)
        self.assertNotEqual(other,ranked)

    def test_file_is_new_for_every_interaction(self):
        a=competition_scene_file(self.bot,self.guild,self.player)
        b=competition_scene_file(self.bot,self.guild,self.player)
        try:
            self.assertIsNot(a.fp,b.fp)
            self.assertEqual(a.filename,SCENE_FILE)
            self.assertEqual(b.filename,SCENE_FILE)
            self.assertTrue(a.fp.read(4))
        finally:
            a.close()
            b.close()

    def test_one_continuous_image_and_native_action_rows(self):
        view=self.make_view(self.bot,self.guild,self.player)
        self.assertEqual(len(view.children),1)
        panel=view.children[0]
        self.assertIsInstance(panel,discord.ui.Container)
        self.assertEqual(len(panel.children),3)
        self.assertIsInstance(panel.children[0],discord.ui.MediaGallery)
        self.assertEqual(len(panel.children[0].items),1)
        self.assertEqual(len(panel.children[0].items),1)
        self.assertTrue(all(not isinstance(child,discord.ui.TextDisplay)
                            for child in panel.children))
        self.assertTrue(all(not isinstance(child,discord.ui.Section)
                            for child in panel.children))
        actions=[child for child in panel.children
                 if isinstance(child,discord.ui.ActionRow)]
        self.assertEqual(len(actions),2)
        self.assertEqual(
            [button.label for row in actions for button in row.children],
            ["Participer","Mes défis","Top 10","Mon rang","Règlement"],
        )
        self.assertEqual(sum(len(row.children) for row in actions),5)


class EmojiArtTests(unittest.TestCase):
    def tearDown(self):
        ICONS.install([])

    def test_ten_original_pngs_fit_discord_application_limits(self):
        self.assertEqual(len(EMOJI_NAMES),10)
        assets=[]
        for name in EMOJI_NAMES:
            data=render_emoji(name)
            image=Image.open(io.BytesIO(data))
            self.assertEqual(image.format,"PNG")
            self.assertEqual(image.size,(SIZE,SIZE))
            self.assertEqual(image.mode,"RGBA")
            self.assertLessEqual(len(data),256*1024)
            self.assertGreater(len(data),800)
            self.assertLess(image.getpixel((0,0))[3],220)
            assets.append(data)
        self.assertEqual(len(set(assets)),len(assets))

    def test_creation_and_second_start_are_idempotent(self):
        class FakeEmoji:
            def __init__(self,name):
                self.name=name
            def __str__(self):
                return "<:testemoji:123456789012345678>"

        class Bot:
            def __init__(self):
                self.items=[]
                self.created=[]
                self.user=None

            async def fetch_application_emojis(self):
                return list(self.items)

            async def create_application_emoji(self,*,name,image):
                self.created.append((name,image))
                item=FakeEmoji(name)
                self.items.append(item)
                return item

        bot=Bot()
        async def both():
            first=await ensure_application_emojis(bot)
            second=await ensure_application_emojis(bot)
            return first,second
        first,second=asyncio.run(both())
        self.assertEqual(first["failed"],[])
        self.assertEqual(set(first["created"]),set(EMOJI_NAMES))
        self.assertEqual(second["created"],[])
        self.assertEqual(len(bot.created),len(EMOJI_NAMES))
        self.assertTrue(all(raw[:4]==b"\x89PNG" for _,raw in bot.created))
        self.assertEqual(len(ICONS.by_key),len(EMOJI_NAMES))


if __name__=="__main__":
    unittest.main()
