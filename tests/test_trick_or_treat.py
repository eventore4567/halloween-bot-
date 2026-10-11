"""Regression tests for the stand-alone Halloween /trickortreat manor."""
from __future__ import annotations

import asyncio
import io
import sqlite3
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
    HEIGHT, WIDTH, TrickOrTreatView, DOOR_RIDDLES, banner_bytes, _font, _fit,
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
        self.assertEqual(self.db.trick_status(10,20,now=102)["wait"],29)
        second=self.db.play_trick(10,20,0,now=102)
        self.assertEqual(second,{"status":"cooldown","wait":29})
        self.assertEqual(self.db.profile(10,20)["candies"],first["amount"])

    def test_legacy_15_minute_cooldown_is_shortened_once(self):
        # Simulate a DB containing historical 900-second timers, then restart.
        self.db.award(4,8,250)
        self.db.buy(4,8,"hat",50)
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO cooldowns "
                "(guild_id,user_id,action,ready_at) VALUES (4,8,'trick',1900)"
            )
            cur.execute(
                "DELETE FROM applied_migrations "
                "WHERE name='trick_cooldown_900_to_30_v1'"
            )
        self.db.close()
        self.db=Store(self.path)
        self.assertEqual(self.db.trick_status(4,8,now=1001)["wait"],29)
        self.assertEqual(self.db.profile(4,8)["candies"],200)
        self.assertEqual(self.db.inventory(4,8)[0]["quantity"],1)
        self.db.close()
        self.db=Store(self.path)
        # Idempotency: a second startup must NOT shorten new 30s timers.
        self.assertEqual(self.db.trick_status(4,8,now=1001)["wait"],29)
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE cooldowns SET ready_at=2000 "
                "WHERE guild_id=4 AND user_id=8 AND action='trick'"
            )
        self.db.close()
        self.db=Store(self.path)
        self.assertEqual(self.db.trick_status(4,8,now=1999)["wait"],1)

    def test_can_pick_again_after_thirty_seconds(self):
        with patch("halloween_bot.storage.random.choices",return_value=["treat"]):
            first=self.db.play_trick(1,3,0,now=1000)
            self.assertEqual(first["status"],"ok")
            self.assertEqual(self.db.play_trick(1,3,2,now=1029)["status"],"cooldown")
            second=self.db.play_trick(1,3,2,now=1030)
        self.assertEqual(second["status"],"ok")
        self.assertEqual(second["plays"],2)
        self.assertEqual(self.db.profile(1,3)["candies"],
                         first["amount"]+second["amount"])

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

    def test_unicode_font_contains_actual_french_glyphs(self):
        """Accents and separators must not become fallback tofu squares."""
        font=_font(42)
        self.assertIn("VeraBd.ttf",str(font.path))
        for symbol in ("É","é","ê","è","à","œ","•","—","×"):
            mask=bytes(font.getmask(symbol))
            self.assertGreater(sum(mask),1000,symbol)
            self.assertNotEqual(mask,bytes(font.getmask("□")),symbol)
        self.assertLessEqual(_fit("LES LÉGENDES",725,size=61),61)

    def test_inventory_and_legendary_item_render_with_accents(self):
        for text in ("Citrouille légendaire","Le chêne oublié",
                     "SÉRIE","LES LÉGENDES"):
            self.assertGreater(sum(bytes(_font(25).getmask(text))),1000)
        data=banner_bytes(
            "inventory",1200,2,inventory=[("Citrouille légendaire",1)]
        )
        image=Image.open(io.BytesIO(data))
        self.assertEqual(image.size,(WIDTH,HEIGHT))
        self.assertGreater(len(data),10000)

    def test_manor_screens_are_landscape_and_render(self):
        outcome={"kind":"jackpot","amount":350,"candies":550,
                 "streak":2,"rare":True}
        for stage, extras in (
            ("intro",{}),
            ("opening",{"selected":1}),
            ("riddle",{"selected":1,"riddle":DOOR_RIDDLES[0]}),
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

    def test_slash_command_public_during_cooldown(self):
        from halloween_bot.games import Games
        self.db.play_trick(1,2,1)
        sent=[]
        class Response:
            async def send_message(self,**kw):
                sent.append(kw)
        async def original_response():
            return SimpleNamespace(id=123)
        interaction=SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=2,bot=False),
            app_permissions=SimpleNamespace(attach_files=True),
            response=Response(),
            original_response=original_response,
        )
        async def run():
            cog=Games(self.bot)
            await Games.trickortreat.callback(cog,interaction)
        asyncio.run(run())
        self.assertEqual(len(sent),1)
        self.assertIs(sent[0]["ephemeral"],False)
        self.assertEqual(len(sent[0]["view"].children[1].children),5)
        self.assertFalse(any(b.disabled for b in
                             sent[0]["view"].children[1].children[:3]))

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

    def test_during_cooldown_doors_stay_clickable_and_browsing_stays_open(self):
        self.db.play_trick(1,2,0)
        view=TrickOrTreatView(self.bot,1,2)
        buttons=view.children[1].children
        self.assertTrue(all(not button.disabled for button in buttons[:3]))
        self.assertTrue(all(not button.disabled for button in buttons[3:]))
        illustration=view._view_file()
        self.assertEqual(illustration.filename,"trickortreat-manoir.jpg")

    def test_four_result_scenes_have_distinct_visuals(self):
        sample={"amount":145,"candies":530,"streak":2,"rare":False}
        samples={}
        for kind in ("treat","jackpot","trick","nothing"):
            reward={**sample,"kind":kind,"rare":kind=="jackpot"}
            data=banner_bytes("result",530,2,result=reward,
                              selected=1,remaining=630)
            img=Image.open(io.BytesIO(data)).convert("RGB")
            self.assertEqual(img.size,(WIDTH,HEIGHT))
            self.assertGreater(len(data),9000)
            # Each story must have artwork, not the same generic four lines.
            samples[kind]=img.getpixel((330,420))
        self.assertEqual(len(set(samples.values())),4)

    def test_collection_presents_existing_items_and_locked_catalogue(self):
        data=banner_bytes(
            "inventory",1200,3,
            inventory=[("legendary_pumpkin","Citrouille légendaire",1),
                       ("cape","Cape de vampire",2)]
        )
        self.assertGreater(len(data),9000)
        self.assertEqual(Image.open(io.BytesIO(data)).size,(WIDTH,HEIGHT))
        # Previously generated two-field test fixtures remain supported.
        legacy=banner_bytes("inventory",100,0,
                            inventory=[("Citrouille légendaire",1)])
        self.assertGreater(len(legacy),9000)

    def test_replay_displays_wait_and_checks_current_cooldown(self):
        self.db.play_trick(1,2,0)
        view=TrickOrTreatView(self.bot,1,2)
        view.stage="result"
        view.result={"kind":"treat","amount":40,"candies":40,
                     "streak":1,"rare":False}
        view._draw()
        buttons=view.children[1].children
        self.assertIn("Rejouer (",buttons[0].label)
        self.assertEqual(buttons[0].style,discord.ButtonStyle.secondary)
        self.assertEqual(len(buttons),3)
        self.assertTrue(all(not b.disabled for b in buttons))

    def test_three_choices_riddle_without_gray_container(self):
        view=TrickOrTreatView(self.bot,1,2)
        view.stage="riddle"
        view.selected=1
        view.riddle=DOOR_RIDDLES[0]
        view._draw()
        self.assertEqual(len(view.children),2)
        self.assertIsInstance(view.children[0],discord.ui.MediaGallery)
        row=view.children[1]
        self.assertEqual(len(row.children),4)
        self.assertEqual([button.label for button in row.children[:3]],[
            f"{letter} · {choice}" for letter,choice
            in zip("ABC",DOOR_RIDDLES[0][1])
        ])
        self.assertEqual(row.children[-1].label,"Changer de porte")
        self.assertTrue(all(not button.disabled for button in row.children))
        self.assertEqual(self.db.trick_status(1,2)["wait"],0)
        image=view._view_file()
        self.assertEqual(image.filename,"trickortreat-manoir.jpg")

    def test_wrong_answer_cancel_and_correct_answer_gate_rewards(self):
        class Response:
            def is_done(self):
                return False
            async def edit_message(self,**kwargs):
                pass
            async def send_message(self,*args,**kwargs):
                pass
        async def run():
            view=TrickOrTreatView(self.bot,1,2)
            def interaction():
                async def edit_original_response(**kwargs):
                    pass
                return SimpleNamespace(
                    user=SimpleNamespace(id=2,bot=False),
                    guild=SimpleNamespace(id=1),
                    response=Response(),
                    edit_original_response=edit_original_response,
                )
            with patch("halloween_bot.trick_or_treat.random.choice",
                       return_value=DOOR_RIDDLES[0]):
                await view.choose(interaction(),1)
                self.assertEqual(view.stage,"riddle")
                self.assertEqual(view.selected,1)
                self.assertEqual(self.db.trick_status(1,2)["wait"],0)
                self.assertEqual(self.db.profile(1,2)["candies"],0)

                # Wrong choice cannot mint rewards or start cooldown.
                await view.answer(interaction(),0)
                self.assertEqual(view.stage,"riddle")
                self.assertEqual(view.wrong_attempts,1)
                self.assertEqual(self.db.trick_status(1,2)["wait"],0)
                self.assertEqual(self.db.profile(1,2)["candies"],0)

                # No penalty for backing out to change the door.
                await view.cancel_riddle(interaction())
                self.assertEqual(view.stage,"intro")
                self.assertIsNone(view.selected)
                self.assertEqual(self.db.trick_status(1,2)["wait"],0)
                await view.choose(interaction(),2)
                self.assertEqual(view.stage,"riddle")

            with patch("halloween_bot.storage.random.choices",
                       return_value=["jackpot"]):
                # A fast double click cannot award the treasure twice.
                await asyncio.gather(
                    view.answer(interaction(),1),
                    view.answer(interaction(),1),
                )
            return view
        view=asyncio.run(run())
        self.assertEqual(view.stage,"result")
        self.assertEqual(view.wrong_attempts,0)
        self.assertEqual(self.db.inventory(1,2)[0]["quantity"],1)
        self.assertEqual(self.db.trick_status(1,2)["streak"],1)
        self.assertGreater(self.db.profile(1,2)["candies"],0)

    def test_owner_only_controls_the_riddle(self):
        view=TrickOrTreatView(self.bot,1,2)
        view.stage="riddle"
        view.selected=0
        view.riddle=DOOR_RIDDLES[0]
        notices=[]
        class Response:
            async def send_message(self, content, **kwargs):
                notices.append((content,kwargs))
        async def test():
            other=SimpleNamespace(
                guild=SimpleNamespace(id=1),
                user=SimpleNamespace(id=3,bot=False),
                response=Response(),
            )
            return await view.interaction_check(other)
        self.assertFalse(asyncio.run(test()))
        self.assertEqual(len(notices),1)
        self.assertEqual(self.db.trick_status(1,2)["wait"],0)




if __name__ == "__main__":
    unittest.main()
