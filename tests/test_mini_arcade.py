"""Regression tests for the seven virtual-candy arcade minigames.

No game must write points to the 1000€ skill-tournament leaderboard.
Tests cover double-click safety, progression, cooldown, image layout and
separation of cash-prize standings from casual virtual rewards.
"""
from __future__ import annotations

import asyncio
import io
import random
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord
from PIL import Image

from halloween_bot.mini_art import HEIGHT, WIDTH, banner_bytes
from halloween_bot.mini_engine import (
    COFFIN_REWARDS, MODES, MiniSession, TTL_SECONDS,
)
from halloween_bot.mini_arcade import (
    ArcadeHub, MiniGameView, MiniArcade, COOLDOWN_SECONDS
)
from halloween_bot.quiz_content import generate_question, generate_film
from halloween_bot.quiz_games import MultipleChoice
from halloween_bot.storage import Store
from halloween_bot.competition_store import Competition
from halloween_bot.common import ICONS


class EngineTests(unittest.TestCase):
    def test_all_seven_games_have_unique_rules_and_choices(self):
        self.assertEqual(len(MODES),7)
        for mode in MODES:
            session=MiniSession(mode,now=5000,rng=random.Random(9))
            self.assertGreaterEqual(len(session.options()),1)
            self.assertFalse(session.done)
            self.assertEqual(session.deadline,5000+TTL_SECONDS)

    def test_rune_memory_cannot_cheat_before_reveal(self):
        s=MiniSession("memoire",now=100,rng=random.Random(4))
        self.assertFalse(s.available(102))
        self.assertEqual(s.choose(s.sequence[0],now=102).status,"waiting")
        self.assertEqual(s.step,0)
        for n,index in enumerate(s.sequence):
            result=s.choose(index,now=107+n)
        self.assertEqual(result.status,"won")
        self.assertEqual(result.reward,160)
        self.assertEqual(s.choose(s.sequence[-1],now=115).status,"used")

    def test_labyrinth_three_right_answers_required(self):
        s=MiniSession("labyrinthe",now=100,rng=random.Random(2))
        for i,(_,answer) in enumerate(s.puzzles):
            result=s.choose(answer,now=105+i)
        self.assertEqual(result.status,"won")
        self.assertEqual(result.reward,150)
        self.assertTrue(s.done)

    def test_potion_ends_after_one_wrong_ingredient(self):
        s=MiniSession("chaudron",now=50,rng=random.Random(5))
        correct=s.puzzles[0][1]
        self.assertEqual(s.choose((correct+1)%4,now=51).status,"lost")
        self.assertEqual(s.choose(correct,now=52).status,"used")

    def test_reflex_punishes_early_click_and_rewards_speed(self):
        s=MiniSession("reflexe",now=100,rng=random.Random(0))
        self.assertEqual(s.choose(0,now=101).status,"waiting")
        self.assertEqual(s.choose(0,now=s.ready_at+0.5).reward,170)
        self.assertEqual(s.choose(0,now=s.ready_at+1).status,"used")

    def test_coffins_only_one_free_pick(self):
        s=MiniSession("coffres",now=100,rng=random.Random(7))
        self.assertEqual(sorted(s.chest_rewards),sorted(COFFIN_REWARDS))
        reward=s.chest_rewards[0]
        first=s.choose(0,now=103)
        self.assertEqual(first.reward,reward)
        self.assertTrue(s.done)
        self.assertEqual(s.choose(1,now=104).status,"used")

    def test_demon_dice_and_ghost_use_one_guess(self):
        for mode in ("des","fantomes"):
            s=MiniSession(mode,now=100,rng=random.Random(8))
            result=s.choose(0,now=102)
            self.assertIn(result.status,("won","lost"))
            self.assertTrue(s.done)
            self.assertEqual(s.choose(0,now=103).status,"used")

    def test_timeout_aborts_any_rewards(self):
        for mode in MODES:
            s=MiniSession(mode,now=200,rng=random.Random(3))
            result=s.choose(0,now=200+TTL_SECONDS)
            self.assertEqual(result.status,"timeout")
            self.assertEqual(result.reward,0)
            self.assertEqual(s.choose(0,now=300).status,"used")


class ArcadeUiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Store(str(Path(self.tmp.name)/"game.sqlite3"))
        self.bot=SimpleNamespace(
            store=self.db,
            competition=Competition(self.db),
        )
        self.owner=17
        self.guild=27
        ICONS.install([])

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
        ICONS.install([])

    def test_images_are_wide_and_no_embedded_alt_overlay(self):
        for name in (*MODES,"menu","quiz"):
            data=banner_bytes(name)
            image=Image.open(io.BytesIO(data))
            self.assertEqual(image.size,(WIDTH,HEIGHT))
            self.assertGreater(WIDTH,HEIGHT)
            self.assertGreater(len(data),6000)

    def test_every_mode_has_its_own_slash_command(self):
        """Discord discovers seven direct slash commands, not only /jeux."""
        names=("memoire","reflexe","labyrinthe","chaudron",
               "coffres","des","fantomes")
        self.assertEqual(set(names),set(MODES))
        for name in names:
            slash=getattr(MiniArcade,name)
            self.assertIsInstance(slash,discord.app_commands.Command)
            self.assertEqual(slash.name,name)
            self.assertTrue(slash.description)

    def test_direct_commands_launch_real_games_without_jeux_hub(self):
        class Response:
            def __init__(self):
                self.sent=[]
            def is_done(self):
                return False
            async def send_message(self,*args,**kwargs):
                self.sent.append((args,kwargs))

        async def run():
            for count, mode in enumerate(MODES):
                response=Response()
                uid=self.owner+count
                guild=SimpleNamespace(id=self.guild)
                user=SimpleNamespace(id=uid,bot=False)
                async def original_response():
                    return SimpleNamespace(id=700+uid)
                interaction=SimpleNamespace(
                    guild=guild,user=user,response=response,
                    original_response=original_response,
                    app_permissions=SimpleNamespace(attach_files=True)
                )
                await getattr(MiniArcade,mode).callback(
                    MiniArcade(self.bot),interaction
                )
                self.assertEqual(len(response.sent),1)
                _,kwargs=response.sent[0]
                self.assertIs(kwargs["ephemeral"],False)
                game=kwargs["view"]
                self.assertIsInstance(game,MiniGameView)
                self.assertEqual(game.session.mode,mode)
                self.assertEqual(game.owner_id,uid)
                self.assertEqual(game.guild_id,self.guild)
                self.assertEqual(game.message.id,700+uid)
                self.assertEqual(kwargs["file"].filename,"halloween-arcade.jpg")
                self.assertIsInstance(game.children[0],discord.ui.MediaGallery)
                self.assertGreater(len(game.children[-1].children),0)
                self.assertFalse(any(isinstance(c,discord.ui.Container)
                                     for c in game.children))
        asyncio.run(run())

    def test_direct_and_jeux_hub_share_one_cooldown(self):
        class Response:
            def __init__(self):
                self.sent=[]
            def is_done(self):
                return False
            async def send_message(self,*args,**kwargs):
                self.sent.append((args,kwargs))

        async def run():
            async def interact():
                response=Response()
                i=SimpleNamespace(
                    guild=SimpleNamespace(id=self.guild),
                    user=SimpleNamespace(id=self.owner,bot=False),
                    response=response,
                    app_permissions=SimpleNamespace(attach_files=True),
                )
                async def original_response():
                    return SimpleNamespace(id=999)
                i.original_response=original_response
                return i,response

            first,response=await interact()
            await MiniArcade.coffres.callback(MiniArcade(self.bot),first)
            self.assertEqual(len(response.sent),1)
            hub=ArcadeHub(self.bot,self.owner,self.guild)
            second,blocked=await interact()
            await hub.launch(second,"coffres")
            self.assertEqual(len(blocked.sent),1)
            _,warning=blocked.sent[0]
            self.assertTrue(warning.get("ephemeral"))
            self.assertNotIn("view",warning)

            # A different game is immediately available.
            third,other=await interact()
            await MiniArcade.des.callback(MiniArcade(self.bot),third)
            self.assertEqual(other.sent[0][1]["view"].session.mode,"des")
        asyncio.run(run())

    def test_direct_launch_without_image_permission_does_not_spend_cooldown(self):
        class Response:
            def __init__(self):
                self.sent=[]
            def is_done(self):
                return False
            async def send_message(self,*args,**kwargs):
                self.sent.append(kwargs)

        async def run():
            async def invoke(allow):
                response=Response()
                interaction=SimpleNamespace(
                    guild=SimpleNamespace(id=self.guild),
                    user=SimpleNamespace(id=self.owner,bot=False),
                    response=response,
                    app_permissions=SimpleNamespace(attach_files=allow)
                )
                async def original_response():
                    return SimpleNamespace(id=1001)
                interaction.original_response=original_response
                await MiniArcade.labyrinthe.callback(
                    MiniArcade(self.bot),interaction
                )
                return response.sent
            denied=await invoke(False)
            self.assertEqual(len(denied),1)
            self.assertTrue(denied[0]["ephemeral"])
            allowed=await invoke(True)
            self.assertEqual(len(allowed),1)
            self.assertIs(allowed[0]["ephemeral"],False)
            self.assertEqual(allowed[0]["view"].session.mode,"labyrinthe")
        asyncio.run(run())

    def test_hub_has_seven_buttons_without_grey_container(self):
        async def build():
            return ArcadeHub(self.bot,self.owner,self.guild)
        view=asyncio.run(build())
        self.assertEqual(len(view.children),4)
        self.assertIsInstance(view.children[0],discord.ui.MediaGallery)
        self.assertEqual(
            [len(row.children) for row in view.children
             if isinstance(row,discord.ui.ActionRow)], [4,3]
        )
        self.assertFalse(any(isinstance(c,discord.ui.Container)
                             for c in view.children))

    def test_game_buttons_match_engine_options_and_disable_before_reveal(self):
        async def build():
            return {mode:MiniGameView(self.bot,self.guild,self.owner,mode)
                    for mode in MODES}
        views=asyncio.run(build())
        for mode,view in views.items():
            self.assertEqual(len(view.children),3)
            self.assertIsInstance(view.children[0],discord.ui.MediaGallery)
            buttons=view.children[-1].children
            self.assertEqual(len(buttons),len(view.session.options()))
            self.assertTrue(
                all(button.disabled for button in buttons)
                if mode in ("memoire","reflexe")
                else all(not button.disabled for button in buttons)
            )

    def test_owner_and_guild_binding(self):
        async def check():
            view=MiniGameView(self.bot,self.guild,self.owner,"coffres")
            reports=[]
            class Response:
                def is_done(self):
                    return False
                async def send_message(self,content,ephemeral=False):
                    reports.append(content)
            wrong=SimpleNamespace(
                guild=SimpleNamespace(id=self.guild),
                user=SimpleNamespace(id=self.owner+1,bot=False),
                response=Response(),
            )
            self.assertFalse(await view.interaction_check(wrong))
            self.assertTrue(reports)
            return view
        asyncio.run(check())

    def test_reward_booked_once_with_two_simultaneous_clicks(self):
        async def exercise():
            view=MiniGameView(self.bot,self.guild,self.owner,"coffres")
            class Response:
                async def edit_message(self,**kwargs):
                    await asyncio.sleep(0)
                def is_done(self):
                    return False
                async def send_message(self,*args,**kwargs):
                    pass
            user=SimpleNamespace(id=self.owner,bot=False)
            interaction=lambda:SimpleNamespace(
                guild=SimpleNamespace(id=self.guild),
                user=user,response=Response()
            )
            idx=next(i for i,n in enumerate(view.session.chest_rewards) if n>0)
            win=view.session.chest_rewards[idx]
            await asyncio.gather(
                view.pick(interaction(),idx),
                view.pick(interaction(),idx),
            )
            return win,view.session
        reward,session=asyncio.run(exercise())
        self.assertTrue(session.done)
        self.assertEqual(self.db.profile(self.guild,self.owner)["candies"],reward)
        self.assertIsNone(self.bot.competition.season(self.guild))

    def test_quiz_film_and_trivia_share_flat_style(self):
        async def build():
            return (
                MultipleChoice(self.guild,generate_question("horreur","facile")),
                MultipleChoice(self.guild,generate_film("facile"),film=True)
            )
        for view in asyncio.run(build()):
            self.assertEqual(len(view.children),4)
            self.assertIsInstance(view.children[0],discord.ui.MediaGallery)
            self.assertFalse(any(isinstance(c,discord.ui.Container)
                                 for c in view.children))
            self.assertEqual(
                sum(len(row.children) for row in view.children
                    if isinstance(row,discord.ui.ActionRow)),4
            )


if __name__=="__main__":
    unittest.main()
