"""Regression tests for the stand-alone Halloween /trickortreat manor."""
from __future__ import annotations

import asyncio
import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import discord
from PIL import Image

from halloween_bot.common import ICONS
from halloween_bot.storage import Store
from halloween_bot.trick_or_treat import (
    HEIGHT, WIDTH, TrickOrTreatView, banner_bytes,
)


class TrickStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.temp.name)/"trick.sqlite3")
        self.db=Store(self.path)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_cooldown_not_consumed_until_door_is_picked(self):
        self.assertEqual(self.db.trick_status(10,20,now=100)["wait"],0)
        self.assertEqual(self.db.trick_status(10,20,now=101)["wait"],0)
        with patch("halloween_bot.storage.random.choices",return_value=["treat"]):
            first=self.db.play_trick(10,20,0,now=101)
        self.assertEqual(first["status"],"ok")
        self.assertEqual(self.db.trick_status(10,20,now=102)["wait"],899)
        second=self.db.play_trick(10,20,0,now=102)
        self.assertEqual(second,{"status":"cooldown","wait":899})
        self.assertEqual(self.db.profile(10,20)["candies"],first["amount"])

    def test_rare_item_persists_across_database_reopen(self):
        with patch("halloween_bot.storage.random.choices",return_value=["jackpot"]), \
             patch("halloween_bot.storage.random.randint",return_value=350):
            outcome=self.db.play_trick(1,2,1,now=1000)
        self.assertTrue(outcome["rare"])
        self.assertEqual(outcome["streak"],1)
        self.assertEqual(self.db.inventory(1,2),
                         [{"item":"legendary_pumpkin","quantity":1}])
        self.db.close()
        self.db=Store(self.path)
        self.assertEqual(self.db.inventory(1,2)[0]["quantity"],1)
        self.assertEqual(self.db.trick_status(1,2,now=1001)["streak"],1)

    def test_penalty_applies_actual_loss_and_never_negative(self):
        self.db.award(1,2,18)
        with patch("halloween_bot.storage.random.choices",return_value=["trick"]), \
             patch("halloween_bot.storage.random.randint",return_value=65):
            lost=self.db.play_trick(1,2,2,now=1000)
        self.assertEqual(lost["amount"],-18)
        self.assertEqual(lost["candies"],0)
        self.assertEqual(self.db.profile(1,2)["candies"],0)
        self.assertEqual(lost["streak"],0)

    def test_two_simultaneous_claims_create_only_one_reward(self):
        claims=[]
        barrier=threading.Barrier(12)
        def hit():
            barrier.wait()
            claims.append(self.db.play_trick(5,7,0,now=1000))
        threads=[threading.Thread(target=hit) for _ in range(12)]
        with patch("halloween_bot.storage.random.choices",return_value=["jackpot"]):
            for th in threads: th.start()
            for th in threads: th.join()
        self.assertEqual(sum(x["status"]=="ok" for x in claims),1)
        self.assertEqual(sum(x["status"]=="cooldown" for x in claims),11)
        self.assertEqual(self.db.inventory(5,7)[0]["quantity"],1)
        self.assertEqual(self.db.trick_status(5,7,now=1001)["streak"],1)

    def test_servers_do_not_share_prizes_or_cooldowns(self):
        with patch("halloween_bot.storage.random.choices",return_value=["treat"]):
            self.db.play_trick(1,2,0,now=1000)
        self.assertEqual(self.db.profile(2,2)["candies"],0)
        self.assertEqual(self.db.trick_status(2,2,now=1001)["wait"],0)


class TrickVisualTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Store(str(Path(self.temp.name)/"trick.sqlite3"))
        self.bot=SimpleNamespace(store=self.db,get_guild=lambda _id:None)
        ICONS.install([])

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
        ICONS.install([])

    def test_manor_screens_are_landscape_and_render(self):
        outcome={"kind":"jackpot","amount":350,"candies":550,
                 "streak":2,"rare":True}
        for stage, extras in (
            ("intro",{}),
            ("opening",{"selected":1}),
            ("result",{"selected":1,"result":outcome}),
            ("inventory",{"inventory":[("Citrouille legendaire",2)]}),
            ("leaderboard",{"leaders":[(1,"Alice",300)]}),
            ("expired",{}),
        ):
            data=banner_bytes(stage,550,2,**extras)
            img=Image.open(io.BytesIO(data))
            self.assertEqual(img.size,(WIDTH,HEIGHT))
            self.assertGreater(WIDTH,HEIGHT)
            self.assertGreater(len(data),8000)

    def test_real_components_without_grey_container(self):
        view=TrickOrTreatView(self.bot,1,2)
        self.assertIsInstance(view,discord.ui.LayoutView)
        self.assertEqual(len(view.children),2)
        self.assertIsInstance(view.children[0],discord.ui.MediaGallery)
        row=view.children[1]
        self.assertIsInstance(row,discord.ui.ActionRow)
        self.assertEqual(len(row.children),5)
        self.assertFalse(any(isinstance(x,discord.ui.Container)
                             for x in view.children))
        self.assertTrue(all(isinstance(x,discord.ui.Button)
                            for x in row.children))

    def test_leaderboard_resolves_uncached_server_nicknames(self):
        self.db.award(1, 987654321012345678, 120)
        requested=[]
        class Guild:
            id=1
            def get_member(self, user_id):
                return None
            async def fetch_member(self, user_id):
                requested.append(user_id)
                return SimpleNamespace(display_name="La Citrouille Dorée")
        class Response:
            def __init__(self):
                self.deferred=False
            def is_done(self):
                return self.deferred
            async def defer(self, *, thinking=False):
                self.deferred=True
        async def run():
            response=Response()
            edited=[]
            async def edit_original_response(**kwargs):
                edited.append(kwargs)
            view=TrickOrTreatView(self.bot,1,987654321012345678)
            interaction=SimpleNamespace(
                guild=Guild(),response=response,
                edit_original_response=edit_original_response
            )
            await view.show_leaderboard(interaction)
            return view,response,edited
        view,response,edited=asyncio.run(run())
        self.assertTrue(response.deferred)
        self.assertEqual(requested,[987654321012345678])
        self.assertEqual(view._leaders,[(1,"La Citrouille Dorée",120)])
        self.assertEqual(view.stage,"leaderboard")
        self.assertEqual(len(edited),1)
        self.assertEqual(len(edited[0]["attachments"]),1)

    def test_no_raw_discord_id_when_membership_unavailable(self):
        self.db.award(1,987654321012345678,55)
        class Guild:
            id=1
            def get_member(self,user_id):
                return None
        async def resolve():
            view=TrickOrTreatView(self.bot,1,2)
            return await view._resolved_leaders(Guild())
        rows=asyncio.run(resolve())
        self.assertEqual(rows,[(1,"Chasseur #1",55)])
        self.assertNotIn("987654321012345678",str(rows))

    def test_during_cooldown_doors_lock_but_browsing_stays_open(self):
        self.db.play_trick(1,2,0)
        view=TrickOrTreatView(self.bot,1,2)
        buttons=view.children[1].children
        self.assertTrue(all(button.disabled for button in buttons[:3]))
        self.assertTrue(all(not button.disabled for button in buttons[3:]))
        illustration=view._view_file()
        self.assertEqual(illustration.filename,"trickortreat-manoir.jpg")

    def test_double_click_mints_reward_once(self):
        class Response:
            def is_done(self):
                return False
            async def edit_message(self,**kwargs):
                pass
            async def send_message(self,*args,**kwargs):
                pass
        async def run():
            v=TrickOrTreatView(self.bot,1,2)
            user=SimpleNamespace(id=2,bot=False)
            def interaction():
                async def edit_original_response(**kwargs):
                    pass
                return SimpleNamespace(
                    user=user,guild=SimpleNamespace(id=1),
                    response=Response(),
                    edit_original_response=edit_original_response,
                )
            with patch("halloween_bot.storage.random.choices",
                       return_value=["jackpot"]):
                await asyncio.gather(
                    v.choose(interaction(),1),
                    v.choose(interaction(),1),
                )
            return v
        view=asyncio.run(run())
        self.assertEqual(view.stage,"result")
        self.assertEqual(self.db.inventory(1,2)[0]["quantity"],1)
        self.assertEqual(self.db.trick_status(1,2)["streak"],1)


if __name__ == "__main__":
    unittest.main()
