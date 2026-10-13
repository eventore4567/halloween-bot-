"""Haunted house, broom race, ritual, reflex, curse and achievements."""
import asyncio
import random
import unittest
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween import config
from halloween.cogs import house, race, reflex, ritual, trophies
from halloween.cogs.curse import loot_amount
from halloween.content import house as H
from halloween.rewards import check_achievements, grant

_real_sleep = asyncio.sleep


async def fast_sleep(delay, *args, **kwargs):
    await _real_sleep(0)


class NewGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def setUp(self):
        self.uid = 7000 + abs(hash(self._testMethodName)) % 1000
        self.user = FakeUser(self.uid, "Explorateur")
        self.store.add_candies(999, self.uid, 5000, "test", boost=False)

    def i(self, **kw):
        return FakeInteraction(user=self.user, client=self.bot, **kw)

    def run_async(self, coro):
        with mock.patch("asyncio.sleep", fast_sleep):
            return asyncio.run(coro)

    def render(self, view):
        view.render()
        return check_layout(view)

    # ------------------------------------------------------------ house
    def test_house_reaches_crypt_with_key(self):
        async def go():
            v = house.HouseView(self.bot, self.i(), True)
            self.render(v)
            outcomes = iter(["key", "treasure", "trap", "ghost"])
            with mock.patch.object(H, "outcome", lambda d, k, rnd=random: next(outcomes)):
                for _ in range(H.DEPTH):
                    await v._choose(0)(self.i())
                    self.render(v)
            self.assertEqual(v.state, "crypt")
            self.assertTrue(v.key)
            await v._crypt(self.i())
            self.assertEqual((v.state, v.ending), ("end", "crypt"))
            self.assertGreater(v.reward.candies, 150)
            self.render(v)
            self.assertEqual(self.store.stats(999, self.uid).get("crypt"), 1)
        self.run_async(go())

    def test_house_monsters_end_the_run(self):
        async def go():
            v = house.HouseView(self.bot, self.i(), True)
            v.bag = 100
            with mock.patch.object(H, "outcome", lambda d, k, rnd=random: "monster"):
                for _ in range(H.LIVES):
                    await v._choose(1)(self.i())
            self.assertEqual((v.state, v.ending), ("end", "dead"))
            self.assertEqual(v.reward.candies, 50)
            self.render(v)
        self.run_async(go())

    def test_house_outcomes(self):
        rnd = random.Random(1)
        kinds = {H.outcome(d, False, rnd) for d in (1, 4) for _ in range(500)}
        self.assertEqual(kinds, set(H.OUTCOMES))
        self.assertNotIn("key", {H.outcome(2, True, rnd) for _ in range(500)})

    # ------------------------------------------------------------ race
    def test_race_win_and_loss(self):
        async def go():
            for forced, expect_win in ((0, True), (1, False)):
                v = race.RaceView(self.bot, self.i(), True)
                self.render(v)
                before = self.store.candies(999, self.uid)
                with mock.patch.object(race.random, "randrange", lambda n: forced):
                    await v._go(0)(self.i())
                self.assertEqual(v.state, "done")
                self.render(v)
                delta = self.store.candies(999, self.uid) - before
                if expect_win:
                    self.assertGreaterEqual(delta, int(100 * race.PAYOUT) - 100)
                else:
                    self.assertLessEqual(delta, -100 + 600)  # achievements may pay a bonus
                    self.assertEqual(v.reward.candies, 0)
        self.run_async(go())

    # ------------------------------------------------------------ ritual
    def test_ritual_rounds(self):
        async def go():
            v = ritual.RitualView(self.bot, self.i(), True)
            self.render(v)
            await v._start(self.i())
            for _ in range(2):
                v.state = "input"
                for sym in list(v.sequence):
                    await v._tap(sym)(self.i())
            self.assertEqual(v.round, 3)
            v.state = "input"
            wrong = (v.sequence[0] + 1) % 4
            await v._tap(wrong)(self.i())
            self.assertEqual(v.state, "lost")
            self.assertEqual(v.reward.candies, ritual.ritual_reward(2))
            self.render(v)
        self.run_async(go())

    # ------------------------------------------------------------ reflex
    def test_reflex_game(self):
        async def go():
            v = reflex.ReflexView(self.bot, self.i(), True)
            self.render(v)
            await v._begin(self.i())
            self.assertEqual(v.state, "wait")
            await v._early(self.i())
            for _ in range(2):
                v.state = "go"
                v.shown_at -= 0.0
                await v._catch(self.i())
            self.assertEqual(v.state, "done")
            self.assertEqual(len(v.times), 3)
            self.assertIsNone(v.times[0])
            self.render(v)
        self.run_async(go())

    def test_reflex_scoring(self):
        self.assertGreater(reflex.reflex_points(0.5), reflex.reflex_points(1.2))
        self.assertEqual(reflex.reflex_points(None), 0)

    # ------------------------------------------------------------ curse
    def test_loot_bounds(self):
        self.assertEqual(loot_amount(100), 20)
        self.assertEqual(loot_amount(100_000), 400)
        self.assertEqual(loot_amount(1000), 80)

    def test_curse_command(self):
        cog = self.bot.get_cog("Curse")
        victim = FakeUser(self.uid + 1, "Victime")
        self.store.add_candies(999, victim.id, 2000, "t", boost=False)

        async def go():
            with mock.patch("halloween.cogs.curse.random.random", lambda: 0.0):
                inter = self.i()
                await cog.sort.callback(cog, inter, victim)
            self.assertEqual(inter.response.sent[0][0], "send")
            self.assertLess(self.store.candies(999, victim.id), 2000)
            again = self.i()
            await cog.sort.callback(cog, again, victim)  # cooldown -> private notice
            self.assertTrue(again.response.sent[0][1].get("ephemeral"))
        self.run_async(go())

    def test_amulet_blocks_curse(self):
        cog = self.bot.get_cog("Curse")
        victim = FakeUser(self.uid + 2, "Prudent")
        self.store.add_candies(999, victim.id, 2000, "t", boost=False)
        self.store.give_item(999, victim.id, "amulet")

        async def go():
            await cog.sort.callback(cog, self.i(), victim)
        self.run_async(go())
        self.assertEqual(self.store.candies(999, victim.id), 2000)
        self.assertEqual(self.store.item_qty(999, victim.id, "amulet"), 0)

    # ------------------------------------------------------------ achievements
    def test_achievements_unlock_once(self):
        g, u = 999, self.uid + 50
        r = grant(self.store, g, u, 10, 5, "t", stats={"quiz_right": 1})
        self.assertIn("first_quiz", [a[0] for a in r.achievements])
        self.assertIn("Succès débloqué", r.line())
        r2 = grant(self.store, g, u, 10, 5, "t", stats={"quiz_right": 1})
        self.assertNotIn("first_quiz", [a[0] for a in r2.achievements])
        self.assertEqual(check_achievements(self.store, g, u), [])

    def test_achievement_keys_are_measurable(self):
        known = {"quiz_right", "quiz_best_streak", "memory_win", "hunt_best", "hangman_win", "house_escape", "crypt",
                 "duel_win", "boss_win", "drops", "potions", "boosters", "cards", "jackpot", "gifts", "streak",
                 "level", "earned", "exp_win", "show_top", "calendar", "pumpkin_fed", "ouija_best", "ouija_words", "shell_best", "slots_jackpot", "motus_win", "hilo_best", "quests_done", "versus_win", "maze_escape", "c4_win", "pet_level", "roulette_best", "escape_win", "trades", "run_best", "traitor_win", "vampire_win"}
        keys = [a[0] for a in config.ACHIEVEMENTS]
        self.assertEqual(len(keys), len(set(keys)))
        for a in config.ACHIEVEMENTS:
            self.assertIn(a[4], known, a)

    def test_trophy_pages(self):
        async def go():
            v = trophies.TrophyView(self.bot, self.i())
            for page in range(3):
                v.page = page
                self.render(v)
        self.run_async(go())


if __name__ == "__main__":
    unittest.main()


class SeasonalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def run_async(self, coro):
        with mock.patch("asyncio.sleep", fast_sleep):
            return asyncio.run(coro)

    def test_calendar_rewards(self):
        for day in range(1, 32):
            r = config.calendar_reward(day)
            self.assertIn("emoji", r)
        self.assertTrue(config.calendar_reward(31)["legendary"])
        self.assertTrue(config.calendar_reward(13)["cursed"])

    def test_calendar_open_once_per_day(self):
        from halloween.cogs import seasonal
        user = FakeUser(9101, "Calendrier")

        async def go():
            with mock.patch.object(seasonal, "october_day", lambda now=None: (2026, 31)):
                v = seasonal.CalendarView(self.bot, FakeInteraction(user=user, client=self.bot))
                check_layout((v.render(), v)[1])
                await v._open(FakeInteraction(user=user, client=self.bot))
                self.assertIn(31, v.opened())
                legendary = [k for k in self.store.cards(999, user.id) if k.startswith("l_")]
                self.assertEqual(len(legendary), 1)
                before = self.store.candies(999, user.id)
                await v._open(FakeInteraction(user=user, client=self.bot))
                self.assertEqual(self.store.candies(999, user.id), before)
                check_layout((v.render(), v)[1])
            with mock.patch.object(seasonal, "october_day", lambda now=None: (2026, None)):
                v = seasonal.CalendarView(self.bot, FakeInteraction(user=user, client=self.bot))
                check_layout((v.render(), v)[1])
        self.run_async(go())

    def test_giant_pumpkin_stage_rewards(self):
        from halloween.cogs import seasonal
        a, b = FakeUser(9201, "A"), FakeUser(9202, "B")
        for u in (a, b):
            self.store.add_candies(999, u.id, 5000, "t", boost=False)

        async def go():
            v = seasonal.GiantView(self.bot, FakeInteraction(user=a, client=self.bot))
            check_layout((v.render(), v)[1])
            for _ in range(3):
                await v._feed(500)(FakeInteraction(user=a, client=self.bot))
            a_before = self.store.candies(999, a.id)
            b_before = self.store.candies(999, b.id)
            await v._feed(500)(FakeInteraction(user=b, client=self.bot))
            st = v.state()
            self.assertEqual(st["total"], 2000)
            self.assertEqual(config.pumpkin_stage(st["total"]), 1)
            # B crossed the stage: B paid 500 and got back 12 % + stage bonus
            self.assertEqual(self.store.candies(999, b.id), b_before - 500 + int(500 * 0.12) + 40)
            # every earlier feeder is rewarded too
            self.assertEqual(self.store.candies(999, a.id), a_before + int(1500 * 0.12) + 40)
            self.assertIn("GRANDIT", v.flash)
            check_layout((v.render(), v)[1])
        self.run_async(go())

    def test_pumpkin_stages(self):
        self.assertEqual(config.pumpkin_stage(0), 0)
        self.assertEqual(config.pumpkin_stage(150_000), len(config.PUMPKIN_STAGES) - 1)


class OuijaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def i(self, uid):
        return FakeInteraction(user=FakeUser(uid, "Médium"), client=self.bot)

    def test_rounds_and_choices(self):
        from halloween.cogs import ouija
        from halloween.art import ouija as board
        for index, (words, *_rest) in enumerate(ouija.ROUNDS):
            self.assertGreaterEqual(len(words), 4)
            for w in words:
                self.assertTrue(ouija.spelled(w), w)
                self.assertTrue(set(ouija.spelled(w)) <= set(board.POSITIONS), w)
                self.assertLessEqual(len(w), 80)
            answer, choices = ouija.pick_round(index, random.Random(index))
            self.assertEqual(len(set(choices)), 4)
            self.assertIn(answer, choices)
        self.assertEqual(ouija.ouija_reward(3), 40 + 70 + 120 + ouija.PERFECT_BONUS)

    def test_spell_gif_plays_once(self):
        from io import BytesIO
        from PIL import Image
        from halloween.art import ouija as board
        data, seconds = board.spell_gif("BOO", 300, 1)
        img = Image.open(BytesIO(data))
        self.assertGreater(img.n_frames, 10)
        self.assertNotIn("loop", img.info)
        self.assertGreater(seconds, 2)

    def _play(self, uid, wrong_at=None):
        from halloween.cogs import ouija

        async def go():
            with mock.patch.object(ouija.OuijaView, "_arm", lambda self, d, t: None), \
                    mock.patch.object(ouija.board, "spell_gif", lambda w, h, s: (b"GIF", 1.0)), \
                    mock.patch.object(ouija.board, "board_png", lambda s: b"PNG"):
                v = ouija.OuijaView(self.bot, self.i(uid), True)
                v.render()
                check_layout(v)
                await v._start(self.i(uid))
                while v.state == "spell":
                    v.render()
                    check_layout(v)
                    await v._reveal(v.token)
                    self.assertEqual(v.state, "answer")
                    v.render()
                    check_layout(v)
                    if v.round == wrong_at:
                        word = next(w for w in v.choices if w != v.answer)
                    else:
                        word = v.answer
                    await v._guess(word)(self.i(uid))
                self.assertEqual(v.state, "end")
                v.render()
                check_layout(v)
                return v
        return asyncio.run(go())

    def test_perfect_seance(self):
        v = self._play(8101)
        self.assertEqual(v.correct, 3)
        self.assertGreaterEqual(v.reward.candies, 290)
        self.assertIn("ach:ouija_perfect", self.store.owned(999, 8101))

    def test_wrong_answer_ends(self):
        v = self._play(8102, wrong_at=2)
        self.assertEqual(v.correct, 1)
        self.assertEqual(self.store.stats(999, 8102).get("ouija_words"), 1)


class ShellTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def test_swaps_track_the_candy(self):
        from halloween.art import shell as art
        from halloween.cogs import shell
        rnd = random.Random(3)
        swaps = shell.make_swaps(9, rnd)
        self.assertTrue(all(a != b for a, b in swaps))
        self.assertTrue(all({*x} != {*y} for x, y in zip(swaps, swaps[1:])))
        slot = 2
        for a, b in swaps:
            slot = b if slot == a else a if slot == b else slot
        frames, durations, end = art.shuffle_frames(2, swaps, 2)
        self.assertEqual(end, slot)
        self.assertEqual(len(frames), len(durations))
        self.assertTrue(art.reveal_png(end, (end + 1) % 3).startswith(b"\x89PNG"))
        self.assertEqual(shell.shell_reward(3), 35 + 70 + 130 + shell.PERFECT_BONUS)

    def _play(self, uid, wrong_at=None):
        from halloween.cogs import shell

        async def go():
            with mock.patch.object(shell.ShellView, "_arm", lambda self, d, t: None), \
                    mock.patch.object(shell.art, "shuffle_gif", lambda c, s, st: (b"GIF", 1.0, 1)), \
                    mock.patch.object(shell.art, "still_png", lambda: b"PNG"), \
                    mock.patch.object(shell.art, "reveal_png", lambda c, ch: b"PNG"):
                i = lambda: FakeInteraction(user=FakeUser(uid, "Lynx"), client=self.bot)  # noqa: E731
                v = shell.ShellView(self.bot, i(), True)
                v.render()
                check_layout(v)
                await v._start(i())
                while v.state == "shuffle":
                    v.render()
                    check_layout(v)
                    await v._ask(v.token)
                    v.render()
                    check_layout(v)
                    await v._pick(0 if v.round == wrong_at else v.slot)(i())
                self.assertEqual(v.state, "end")
                v.render()
                check_layout(v)
                return v
        return asyncio.run(go())

    def test_perfect_game(self):
        v = self._play(8201)
        self.assertEqual(v.correct, 3)
        self.assertIn("ach:shell_perfect", self.store.owned(999, 8201))

    def test_wrong_pick_ends(self):
        v = self._play(8202, wrong_at=1)
        self.assertEqual((v.correct, v.reward.candies), (0, 0))
