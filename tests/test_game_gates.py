"""Real game-cog integration coverage for the reusable Halloween riddle gate."""
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
from halloween_bot.games import Games, BossView, DuelView, ExpeditionView
from halloween_bot.riddle_gate import (
    RiddleGate, RewardScene, FILENAME, make_gate_art, make_reward_art
)
from halloween_bot.storage import Store
from halloween_bot.trick_or_treat import DOOR_RIDDLES


class _Response:
    def __init__(self):
        self.sent=[]
        self.edited=[]
        self.done=False

    def is_done(self):
        return self.done

    async def send_message(self, *args, **kw):
        self.sent.append((args, kw))
        self.done=True

    async def edit_message(self, **kw):
        self.edited.append(kw)
        self.done=True


class GameGateTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.folder.name)/"gates.sqlite"))
        self.bot=SimpleNamespace(store=self.store,active_bosses={})
        ICONS.install([])

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()
        ICONS.install([])

    def interaction(self,uid=13,gid=7):
        response=_Response()
        async def original_response():
            return SimpleNamespace(id=51,edit=lambda **kw: None)
        user=SimpleNamespace(id=uid,mention=f"<@{uid}>",bot=False)
        return SimpleNamespace(
            guild=SimpleNamespace(id=gid),user=user,client=self.bot,
            response=response, app_permissions=SimpleNamespace(attach_files=True),
            original_response=original_response,
            message=SimpleNamespace(id=51)
        )

    async def _launch(self,method,*,interaction=None,kwargs=None):
        i=interaction or self.interaction()
        with patch("halloween_bot.riddle_gate.random.choice",
                   return_value=DOOR_RIDDLES[0]):
            await getattr(Games,method).callback(Games(self.bot),i,**(kwargs or {}))
        self.assertEqual(len(i.response.sent),1)
        args,kw=i.response.sent[0]
        self.assertIs(kw["ephemeral"],False)
        self.assertIsInstance(kw["view"],RiddleGate)
        self.assertEqual(len(kw["view"].children),3)
        self.assertEqual(kw["file"].filename,FILENAME)
        self.assertNotIn("embed",kw)
        return i,kw["view"]

    def test_art_is_valid_and_readable(self):
        image=Image.open(io.BytesIO(
            make_gate_art("Le Roi des Citrouilles",DOOR_RIDDLES[0][0])
        ))
        self.assertEqual(image.size,(1280,700))
        for outcome in ("treat","jackpot","trick","nothing"):
            preview=Image.open(io.BytesIO(
                make_reward_art("La citrouille mystérieuse",outcome,95,
                                "Une vieille citrouille mystérieuse !")
            ))
            self.assertEqual(preview.size,(1280,700))

    def test_all_relevant_games_start_with_riddle_instead_of_rewards(self):
        async def run():
            for method,kwargs in (
                ("ghosthunt",{}), ("pumpkin",{}),
                ("expedition",{}), ("boss",{}),
                ("duel",{"adversaire":SimpleNamespace(
                    id=42,mention="<@42>",bot=False)}),
            ):
                i,gate=await self._launch(method,kwargs=kwargs)
                self.assertFalse(gate.finished)
                self.assertEqual(self.store.profile(7,13)["candies"],0)
                self.assertEqual(self.store.trick_status(7,13)["wait"],0)
                self.assertEqual(self.bot.active_bosses,{})
        asyncio.run(run())

    def test_wrong_answers_never_consume_original_game_cooldown(self):
        async def run():
            for name,action in (("ghosthunt","hunt"),("pumpkin","pumpkin"),
                                ("expedition","expedition"),("duel","duel")):
                kw={"adversaire":SimpleNamespace(id=42,mention="<@42>",bot=False)} if name=="duel" else {}
                i,gate=await self._launch(name,kwargs=kw)
                mistake=self.interaction()
                await gate.answer(mistake,0)
                self.assertEqual(len(mistake.response.edited),1)
                self.assertIsNone(mistake.response.edited[0]["embed"])
                self.assertEqual(len(mistake.response.edited[0]["attachments"]),1)
                self.assertFalse(gate.finished)
                self.assertEqual(gate.attempts,1)
                self.assertEqual(self.store.profile(7,13)["candies"],0)
                self.assertEqual(self.store.cooldown(7,13,action,1,now=100),0)
                # The above storage check claims a 1s cooldown in the
                # fictional past, not a real-time reward attempt.
        asyncio.run(run())

    def test_pumpkin_reward_only_after_correct_answer(self):
        async def run():
            i,gate=await self._launch("pumpkin")
            answer=self.interaction()
            with patch("halloween_bot.games.random.choices",return_value=["rare"]), \
                 patch("halloween_bot.games.random.randint",return_value=150):
                await gate.answer(answer,1)
            self.assertTrue(gate.finished)
            self.assertEqual(self.store.profile(7,13)["candies"],150)
            self.assertEqual(self.store.profile(7,13)["pumpkins"],1)
            self.assertEqual(len(answer.response.edited),1)
            result=answer.response.edited[0]
            self.assertIsInstance(result["view"],RewardScene)
            self.assertIsNone(result["embed"])
            self.assertIsNone(result["content"])
            self.assertEqual(len(result["attachments"]),1)
            self.assertEqual(result["attachments"][0].filename,FILENAME)
            self.assertEqual(len(result["view"].children),1)
            self.assertIsInstance(result["view"].children[0],
                                  discord.ui.MediaGallery)
            self.assertFalse(any(isinstance(x,discord.ui.Container)
                                 for x in result["view"].children))
            # A second gate cannot reward again before the real cooldown.
            other,second=await self._launch("pumpkin")
            blocked=self.interaction()
            await second.answer(blocked,1)
            self.assertFalse(second.finished)
            self.assertEqual(self.store.profile(7,13)["candies"],150)
        asyncio.run(run())

    def test_image_free_server_still_runs_with_embed_fallback(self):
        async def run():
            launch=self.interaction()
            launch.app_permissions.attach_files=False
            gate=None
            with patch("halloween_bot.riddle_gate.random.choice",
                       return_value=DOOR_RIDDLES[0]):
                await Games.pumpkin.callback(Games(self.bot),launch)
            sent=launch.response.sent[0][1]
            gate=sent["view"]
            self.assertFalse(gate.has_art)
            self.assertNotIn("file",sent)
            self.assertIsNotNone(sent["embed"])
            answer=self.interaction()
            with (patch("halloween_bot.games.random.choices",
                        return_value=["simple"]),
                  patch("halloween_bot.games.random.randint",
                        return_value=55)):
                await gate.answer(answer,1)
            self.assertTrue(gate.finished)
            result=answer.response.edited[0]
            self.assertIsNotNone(result["embed"])
            self.assertIsNone(result["view"])
            self.assertEqual(result["attachments"],[])
            self.assertEqual(self.store.profile(7,13)["candies"],55)
        asyncio.run(run())

    def test_ghost_reward_contains_no_duplicate_embed(self):
        async def run():
            _,gate=await self._launch("ghosthunt")
            with patch("halloween_bot.games.random.random",return_value=0.0):
                answer=self.interaction()
                await gate.answer(answer,1)
            result=answer.response.edited[0]
            self.assertIsNone(result["embed"])
            self.assertIsNone(result["content"])
            self.assertIsInstance(result["view"],RewardScene)
            self.assertEqual(len(result["attachments"]),1)
            self.assertEqual(self.store.profile(7,13)["candies"],0)
        asyncio.run(run())

    def test_ghosthunt_failure_only_after_riddle(self):
        async def run():
            _,gate=await self._launch("ghosthunt")
            with patch("halloween_bot.games.random.random",return_value=0.0):
                await gate.answer(self.interaction(),1)
            self.assertTrue(gate.finished)
            self.assertEqual(self.store.profile(7,13)["candies"],0)
            self.assertEqual(self.store.profile(7,13)["ghosts"],0)
        asyncio.run(run())

    def test_duel_expedition_and_boss_handoff_keep_same_message(self):
        async def run():
            other=SimpleNamespace(id=42,mention="<@42>",bot=False)
            for name,kwargs,view_class in (
                ("duel",{"adversaire":other},DuelView),
                ("expedition",{},ExpeditionView),
                ("boss",{},BossView),
            ):
                _,gate=await self._launch(name,kwargs=kwargs)
                click=self.interaction()
                await gate.answer(click,1)
                self.assertTrue(gate.finished)
                self.assertEqual(len(click.response.edited),1)
                payload=click.response.edited[0]
                self.assertIsInstance(payload["view"],view_class)
                self.assertEqual(payload["view"].message.id,51)
            self.assertIn(7,self.bot.active_bosses)
            self.assertEqual(self.store.profile(7,13)["candies"],0)
        asyncio.run(run())

    def test_answer_race_one_continuation_only(self):
        async def run():
            _,gate=await self._launch("pumpkin")
            first=self.interaction()
            second=self.interaction()
            with patch("halloween_bot.games.random.choices",return_value=["simple"]), \
                 patch("halloween_bot.games.random.randint",return_value=60):
                await asyncio.gather(gate.answer(first,1),gate.answer(second,1))
            self.assertEqual(self.store.profile(7,13)["candies"],60)
            self.assertEqual(self.store.profile(7,13)["pumpkins"],1)
            self.assertEqual(len(first.response.edited),1)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
