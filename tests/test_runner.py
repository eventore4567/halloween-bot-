"""La Grande Fuite: the 2D runner chased by the Reaper."""
import asyncio
import sys
import time
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.art import runner as art
from halloween.ui import ACTION, SCENE


def stub_clip(*args, **kwargs):
    return b"GIF89a"


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Runner")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def i(self, uid):
        return FakeInteraction(user=FakeUser(uid, "Coureur"), client=self.bot)

    @staticmethod
    def files(inter):
        kind, kwargs = inter.response.sent[-1]
        return [f.filename for f in kwargs["files"]]

    def view(self, uid):
        v = self.mod.RunView(self.bot, self.i(uid), True)
        v._arm = lambda: None  # no real-time timer in tests
        v._set_deadline()
        return v

    def test_clips(self):
        for kind, action in art.OBSTACLES.items():
            for ok, act in ((True, action), (False, None), (False, "jump" if action != "jump" else "slide")):
                frames = art.step_frames(kind, act, ok, "tomb", 3, 3 if ok else 2, 5, 80, "Coureur", 1)
                self.assertGreater(len(frames), 20)
                self.assertEqual(frames[0].size, (art.W, art.H))
        gif = Image.open(BytesIO(art.start_clip("bats", "Coureur", 2)))
        self.assertGreater(gif.n_frames, 15)

    def test_clear_miss_and_capture(self):
        async def go():
            v = self.view(9701)
            v.render()
            check_layout(v)
            with mock.patch.object(self.mod.art, "step_clip", stub_clip):
                v.obstacle = "tomb"
                await v._act("jump", v.index)(self.i(9701))
                self.assertEqual((v.passed, v.lives, v.bag), (1, 3, self.mod.gain(1)))
                self.assertEqual(v._action, ACTION)
                check_layout(v)
                v.obstacle = "zombie"
                await v._act("slide", v.index)(self.i(9701))  # wrong move
                self.assertEqual((v.passed, v.lives), (1, 2))
                v.obstacle = "bats"
                v.deadline = time.time() - 1
                await v._act("slide", v.index)(self.i(9701))  # right move, but too late
                self.assertEqual(v.lives, 1)
                before = self.store.candies(v.guild_id, 9701)
                await v._expire(v.turn)  # the timer runs out: caught
            self.assertEqual(v.state, "caught")
            self.assertTrue(v.finished)
            self.assertEqual(self.store.candies(v.guild_id, 9701) - before, v.reward.candies)
            check_layout(v)
        asyncio.run(go())

    def test_cash_out_and_chapel(self):
        async def go():
            v = self.view(9702)
            with mock.patch.object(self.mod.art, "step_clip", stub_clip):
                for _ in range(self.mod.SHUFFLE_FROM + 1):
                    await v._act(art.OBSTACLES[v.obstacle], v.index)(self.i(9702))
                self.assertEqual(v.passed, self.mod.SHUFFLE_FROM + 1)
                self.assertEqual(sorted(v.order), sorted(self.mod.ACTIONS))
                bag = v.bag
                await v._cash(self.i(9702))
            self.assertEqual(v.state, "cashed")
            self.assertGreaterEqual(v.reward.candies, bag)
            check_layout(v)

            w = self.view(9703)
            w.passed = self.mod.GOAL - 1
            with mock.patch.object(self.mod.art, "step_clip", stub_clip):
                await w._act(art.OBSTACLES[w.obstacle], w.index)(self.i(9703))
            self.assertEqual(w.state, "escaped")
            self.assertGreaterEqual(w.reward.candies, w.bag + self.mod.CHAPEL_BONUS)
            self.assertEqual(self.store.stats(w.guild_id, 9703)["run_best"], self.mod.GOAL)
            self.assertIn("run_25", [a[0] for a in w.reward.achievements])
            self.assertIn("NOUVEAU RECORD DU SERVEUR", w.flash)
            self.assertEqual(self.store.board(w.guild_id, "fuite", 1), [(9703, self.mod.GOAL)])
        asyncio.run(go())

    def test_end_plays_cutscene(self):
        import halloween.ui as ui
        scenes = []

        def fake_scene(key, reward, seed=0, name="", won=None):
            scenes.append((reward.candies, won))
            return b"GIF89a"

        async def go():
            v = self.view(9704)
            v._shows_banner = True
            v.lives = 1
            v.passed, v.bag = 2, 40
            v.obstacle = "pit"
            inter = self.i(9704)
            with mock.patch.object(self.mod.art, "step_clip", stub_clip), mock.patch.object(ui, "cutscene_for", fake_scene):
                await v._act("strike", v.index)(inter)
            self.assertEqual(v.state, "caught")
            kind, kwargs = inter.response.sent[-1]
            self.assertEqual(kind, "edit_original")
            names = [f.filename for f in kwargs.get("attachments", [])]
            self.assertEqual(names, [SCENE])
            self.assertEqual(scenes[0][1], False)  # a quarter of the bag is kept, but it is a defeat
            self.assertGreater(scenes[0][0], 0)
        asyncio.run(go())

    def test_stale_clicks_are_ignored(self):
        async def go():
            v = self.view(9706)
            v.obstacle = "tomb"
            old = v._act("jump", v.index)
            with mock.patch.object(self.mod.art, "step_clip", stub_clip):
                await v._act("jump", v.index)(self.i(9706))
                self.assertEqual(v.passed, 1)
                v.obstacle = "bats"
                await old(self.i(9706))  # a double click on the first obstacle: dropped
                self.assertEqual((v.passed, v.lives), (1, 3))
        asyncio.run(go())

    def test_buttons_shuffle_from_the_eighth_obstacle(self):
        async def go():
            v = self.view(9707)
            shown = []
            with mock.patch.object(self.mod.art, "step_clip", stub_clip), \
                    mock.patch.object(self.mod.random, "shuffle", lambda seq: shown.append(v.passed + 1)):
                for _ in range(self.mod.SHUFFLE_FROM):
                    await v._act(art.OBSTACLES[v.obstacle], v.index)(self.i(9707))
            self.assertEqual(shown[0], self.mod.SHUFFLE_FROM)  # shuffled before obstacle 8 is shown
        asyncio.run(go())

    def test_new_quest_waits_for_the_next_day(self):
        import random
        from halloween import challenges as Q
        old_pool = [q for q in Q.DAILY if q.qid != "d_fuite"]
        for g in range(30):
            self.assertEqual(Q.daily_quests(g, 7, "2026-10-13"),
                             random.Random(f"{g}:7:2026-10-13").sample(old_pool, Q.DAILY_COUNT))
        self.assertTrue(any("d_fuite" in [q.qid for q in Q.daily_quests(g, 7, "2026-10-20")] for g in range(60)))

    def test_open_and_daily_limit(self):
        from halloween import config

        async def go():
            u = 9705
            with mock.patch.object(self.mod.art, "start_clip", stub_clip), \
                    mock.patch.object(self.mod.RunView, "_arm", lambda self: None):
                for _ in range(config.LIMITS["fuite"]):
                    inter = self.i(u)
                    await self.cog.open(inter)
                    self.assertIn(ACTION, self.files(inter))
                inter = self.i(u)
                await self.cog.open(inter)
                self.assertNotIn(ACTION, self.files(inter))
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
