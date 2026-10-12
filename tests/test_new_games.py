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
                 "level", "earned", "exp_win", "show_top"}
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
