"""End-to-end checks for five DIFFERENT Halloween games.

Every game has native controls and an illustrated public panel. No generic
riddle is required for these five games, and no prize is minted twice.
"""
import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import discord
from PIL import Image

from halloween_bot.common import ICONS
from halloween_bot.games import Games
from halloween_bot.adventure_games import (
    GhostHuntView, PumpkinView, ExpeditionView, DuelView, BossView,
    PALETTE, scene_file,
)
from halloween_bot.storage import Store


class Response:
    def __init__(self):
        self.sent=[]
        self.edited=[]
        self.done=False
    def is_done(self): return self.done
    async def send_message(self,*args,**kwargs):
        self.sent.append(kwargs)
        self.done=True
    async def edit_message(self,**kwargs):
        self.edited.append(kwargs)
        self.done=True


class GamesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.temp.name)/"games.sqlite3"))
        self.bot=SimpleNamespace(store=self.store,active_bosses={})
        ICONS.install([])

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
        ICONS.install([])

    def interaction(self,uid=13,gid=7,name=None):
        response=Response()
        async def original_response():
            return SimpleNamespace(id=51)
        return SimpleNamespace(
            guild=SimpleNamespace(id=gid),
            user=SimpleNamespace(id=uid,bot=False,mention=f"<@{uid}>",
                                 display_name=name or f"Chasseur {uid}"),
            client=self.bot,
            response=response,
            app_permissions=SimpleNamespace(attach_files=True),
            original_response=original_response,
        )

    async def launch(self,command,kwargs=None):
        i=self.interaction()
        await getattr(Games,command).callback(Games(self.bot),i,**(kwargs or {}))
        self.assertEqual(len(i.response.sent),1)
        sent=i.response.sent[0]
        self.assertIs(sent["ephemeral"],False)
        self.assertEqual(sent["file"].filename,"crypt-aventure.jpg")
        self.assertIsInstance(sent["view"],discord.ui.LayoutView)
        self.assertEqual(len(sent["view"].children),2)
        self.assertIsInstance(sent["view"].children[0],discord.ui.MediaGallery)
        self.assertEqual(sent["view"].message.id,51)
        self.assertNotIn("embed",sent)
        return sent["view"]

    def test_every_game_art_is_different(self):
        seen=set()
        for kind in PALETTE:
            data=scene_file(kind,"start",lines=["Teste un nouveau décor !"])
            img=Image.open(data.fp)
            self.assertEqual(img.size,(1280,700))
            # Real illustrated identity, not a color change of same castle.
            region=img.crop((140,300,690,530))
            self.assertGreater(len(set(region.getdata())),70)
            seen.add(region.getpixel((120,100)))
        self.assertEqual(len(seen),5)

    def test_unique_game_panels_and_controls(self):
        async def run():
            for name,kwargs,cls,labels in (
                ("ghosthunt",{},GhostHuntView,3),
                ("pumpkin",{},PumpkinView,3),
                ("expedition",{},ExpeditionView,3),
                ("duel",{"adversaire":SimpleNamespace(
                    id=42,bot=False,mention="<@42>",display_name="Rival")},
                    DuelView,2),
                ("boss",{},BossView,3),
            ):
                view=await self.launch(name,kwargs)
                self.assertIsInstance(view,cls)
                self.assertEqual(len(view.children[1].children),labels)
                self.assertEqual(self.store.profile(7,13)["candies"],0)
        asyncio.run(run())

    def test_ghosthunt_is_search_not_an_enigma(self):
        async def run():
            view=await self.launch("ghosthunt")
            self.assertEqual(view.stage,"start")
            self.assertIn(view.PLACES[view.hidden],view.lines[1])
            with patch("halloween_bot.adventure_games.random.random",
                       return_value=.7), \
                 patch("halloween_bot.adventure_games.random.choices",
                       return_value=[("Fantôme test",45,70)]), \
                 patch("halloween_bot.adventure_games.random.randint",
                       return_value=58):
                a=self.interaction()
                await view.search(a,view.hidden)
            self.assertEqual(view.stage,"result")
            self.assertEqual(len(a.response.edited),1)
            self.assertEqual(self.store.profile(7,13)["candies"],58)
            self.assertEqual(self.store.profile(7,13)["ghosts"],1)
            self.assertEqual(a.response.edited[0]["attachments"][0].filename,
                             "crypt-aventure.jpg")
            await view.search(self.interaction(),view.hidden)
            self.assertEqual(self.store.profile(7,13)["candies"],58)
        asyncio.run(run())

    def test_pumpkin_requires_three_hits_and_one_reward(self):
        async def run():
            view=await self.launch("pumpkin")
            await view.select(self.interaction(),1)
            self.assertEqual(view.stage,"crack")
            self.assertEqual(self.store.profile(7,13)["candies"],0)
            await view.hit(self.interaction())
            await view.hit(self.interaction())
            self.assertEqual(view.cracks,2)
            self.assertEqual(self.store.profile(7,13)["candies"],0)
            with patch("halloween_bot.adventure_games.random.choices",
                       return_value=["rare"]), \
                 patch("halloween_bot.adventure_games.random.randint",
                       return_value=170):
                await asyncio.gather(view.hit(self.interaction()),
                                     view.hit(self.interaction()))
            self.assertEqual(view.stage,"result")
            self.assertEqual(self.store.profile(7,13)["candies"],170)
            self.assertEqual(self.store.profile(7,13)["pumpkins"],1)
            self.assertEqual(view.cracks,3)
        asyncio.run(run())

    def test_expedition_has_strategy_before_reward(self):
        async def run():
            view=await self.launch("expedition")
            await view.choose_path(self.interaction(),0)
            self.assertEqual(view.stage,"route")
            self.assertEqual(self.store.profile(7,13)["candies"],0)
            with patch("halloween_bot.adventure_games.random.random",
                       return_value=.99), \
                 patch("halloween_bot.adventure_games.random.randint",
                       return_value=110):
                await view.cautious(self.interaction())
            self.assertEqual(view.stage,"result")
            self.assertEqual(self.store.profile(7,13)["expeditions"],1)
            self.assertGreater(self.store.profile(7,13)["candies"],0)
            self.assertGreater(self.store.cooldown(
                7,13,"expedition",600),0)
        asyncio.run(run())

    def test_duel_has_ten_turns_not_coinflip_on_accept(self):
        async def run():
            rival=SimpleNamespace(id=42,bot=False,mention="<@42>",
                                  display_name="Rival")
            view=await self.launch("duel",{"adversaire":rival})
            accepted=self.interaction(uid=42)
            await view.accept(accepted)
            self.assertEqual(view.stage,"fight")
            self.assertEqual(self.store.profile(7,13)["candies"],0)
            with patch("halloween_bot.adventure_games.random.randint",
                       return_value=32):
                for _ in range(10):
                    if view.finished:break
                    uid=view.players[view.turn]
                    await view.attack(self.interaction(uid=uid))
            self.assertTrue(view.finished)
            self.assertEqual(view.stage,"result")
            self.assertEqual(
                self.store.profile(7,13)["candies"]+
                self.store.profile(7,42)["candies"],150
            )
            self.assertEqual(
                self.store.profile(7,13)["duel_wins"]+
                self.store.profile(7,42)["duel_wins"],1
            )
        asyncio.run(run())

    def test_boss_has_phases_and_pays_every_participant_once(self):
        async def run():
            view=await self.launch("boss")
            self.assertIs(self.bot.active_bosses[7],view)
            with patch("halloween_bot.adventure_games.random.random",
                       return_value=.9), \
                 patch("halloween_bot.adventure_games.random.randint",
                       return_value=82):
                for uid in range(25,32):
                    if view.finished:break
                    await view.attack(self.interaction(uid=uid),"risk")
            self.assertTrue(view.finished)
            self.assertEqual(view.hp,0)
            self.assertNotIn(7,self.bot.active_bosses)
            self.assertEqual(sum(
                self.store.profile(7,uid)["candies"] for uid in view.damage
            ),150*len(view.damage))
            for uid in view.damage:
                self.assertLessEqual(view.hits[uid],3)
        asyncio.run(run())

    def test_non_owner_solo_cannot_press_buttons(self):
        async def run():
            view=await self.launch("pumpkin")
            response=Response()
            other=SimpleNamespace(
                guild=SimpleNamespace(id=7),
                user=SimpleNamespace(id=55,bot=False),response=response)
            allowed=await view.interaction_check(other)
            self.assertFalse(allowed)
            self.assertEqual(self.store.profile(7,55)["candies"],0)
        asyncio.run(run())


if __name__=="__main__":
    unittest.main()
