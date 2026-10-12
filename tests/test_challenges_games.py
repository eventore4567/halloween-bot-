"""Daily/weekly challenges, the haunted slot machine, Motus and Plus ou Moins."""
import asyncio
import random
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween import challenges as Q
from halloween import config
from halloween.rewards import grant

_real_sleep = asyncio.sleep


async def fast_sleep(delay, *args, **kwargs):
    await _real_sleep(0)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def i(self, uid, **kw):
        return FakeInteraction(user=FakeUser(uid, "Joueur"), client=self.bot, **kw)

    def show(self, view):
        view.render()
        return check_layout(view)

    def run_async(self, coro):
        with mock.patch("asyncio.sleep", fast_sleep):
            return asyncio.run(coro)


class ChallengeTest(Base):
    def test_pools_and_reasons(self):
        for q in Q.DAILY + Q.WEEKLY:
            if q.key.startswith("play:") and q.key != "play:any":
                self.assertIn(q.key[5:], Q.GAME_REASONS, q)
            if q.game:
                self.assertIn(q.game, self.bot.openers, q)
        self.assertEqual(len({q.qid for q in Q.DAILY + Q.WEEKLY}), len(Q.DAILY + Q.WEEKLY))
        self.assertRegex(Q.week_key("2026-10-12"), r"^W2026-42$")
        self.assertEqual(Q.daily_quests(1, 2, "2026-10-12"), Q.daily_quests(1, 2, "2026-10-12"))

    def test_progress_completion_and_claim(self):
        g, u = 999, 9301
        quest = Q.Quest("d_test", "Joue 2 parties de test", "play:maison", 2, 111, "house", "house")
        with mock.patch.object(Q, "daily_quests", lambda g, u, day=None: [quest]), \
                mock.patch.object(Q, "weekly_quests", lambda g, u, week=None: []):
            r1 = grant(self.store, g, u, 10, 1, "maison")
            self.assertEqual(r1.quests, [])
            r2 = grant(self.store, g, u, 10, 1, "maison")
            self.assertEqual(r2.quests, [quest])
            self.assertIn("Défi accompli", r2.line())
            before = self.store.candies(g, u)
            total, paid, bonus = Q.claim_all(self.store, g, u)
            self.assertEqual(paid, [quest])
            self.assertTrue(bonus)  # the single daily quest of this patched day is done
            self.assertEqual(self.store.candies(g, u) - before, total)
            self.assertEqual(total, 111 + Q.ALL_DONE_BONUS)
            self.assertEqual(Q.claim_all(self.store, g, u), (0, [], False))
            self.assertEqual(self.store.item_qty(g, u, "ticket"), 1)

    def test_view_renders_and_claims(self):
        from halloween.cogs import challenges as cog

        async def go():
            g, u = 999, 9302
            day = config.today()
            q = Q.daily_quests(g, u, day)[0]
            self.store.bump(g, u, "q:" + q.key, amount=q.goal, day=day)
            v = cog.ChallengesView(self.bot, self.i(u))
            files = await v.extra_files()
            self.assertEqual(files[0].filename, cog.PNG_NAME)
            self.show(v)
            await v._claim(self.i(u))
            self.assertIn("récupérés", v.flash)
            self.show(v)
        self.run_async(go())


class SlotsTest(Base):
    def test_odds_and_payouts(self):
        from halloween.cogs import slots
        rtp = slots.expected_return()
        self.assertTrue(0.85 < rtp < 0.99, rtp)
        self.assertEqual(slots.payout(("crown",) * 3, 10), (1500, "JACKPOT ×150"))
        self.assertEqual(slots.payout(("bat", "bat", "skull"), 100)[0], 110)
        self.assertEqual(slots.payout(("bat", "ghost", "skull"), 100), (0, ""))

    def test_spin_flow(self):
        from halloween.cogs import slots

        async def go():
            u = 9311
            self.store.add_candies(999, u, 1000, "test", boost=False)
            with mock.patch.object(slots.SlotsView, "_arm", lambda self, d, t: None), \
                    mock.patch.object(slots.art, "spin_gif", lambda *a: (b"GIF", 1.0, b"PNG")), \
                    mock.patch.object(slots, "spin", lambda rnd=random: ("crown", "crown", "crown")):
                v = slots.SlotsView(self.bot, self.i(u), True)
                self.show(v)
                await v._set_bet(10)(self.i(u))
                await v._pull(self.i(u))
                self.assertEqual(v.state, "spin")
                self.show(v)
                await v._show(v.token)
                self.assertEqual(v.won, 1500)
                self.show(v)
                self.assertIn("ach:slots_jackpot", self.store.owned(999, u))
        self.run_async(go())

    def test_gif(self):
        from halloween.cogs import slots
        data, seconds, png = slots.art.spin_gif(("bat", "bat", "ghost"), slots.NAMES, slots.COLORS, "PAIRE",
                                                slots.neon.CYAN, True, 1)
        self.assertGreater(Image.open(BytesIO(data)).n_frames, 20)
        self.assertTrue(png.startswith(b"\x89PNG"))


class MotusTest(Base):
    def test_score(self):
        from halloween.cogs.motus import WORDS, normalize, score
        self.assertEqual([s for _l, s in score("SORBETS", "SORCIER")],
                         ["good", "good", "good", "miss", "near", "miss", "miss"])
        self.assertEqual([s for _l, s in score("AABB", "ABAB")], ["good", "near", "near", "good"])
        self.assertEqual(normalize("Sorcière !"), "SORCIERE")
        for w, hint in WORDS:
            self.assertEqual(normalize(w), w)
            self.assertTrue(5 <= len(w) <= 10, w)

    def test_flow(self):
        from halloween.cogs import motus

        async def go():
            u = 9321
            v = motus.MotusView(self.bot, self.i(u), True, word=("FANTOME", "Il traverse les murs"))
            self.assertEqual(len(await v.extra_files()), 1)
            self.show(v)
            await v._ask(self.i(u))
            await v.submit(self.i(u), "abc")
            self.assertIn("7 lettres", v.flash)
            for _ in range(3):
                await v.submit(self.i(u), "FROMAGE")
            self.show(v)
            await v.submit(self.i(u), "fantôme")
            self.assertEqual(v.state, "won")
            self.assertEqual(v.reward.candies, motus.REWARDS[3])
            self.show(v)
            lost = motus.MotusView(self.bot, self.i(u + 1), True, word=("FANTOME", "x"))
            for _ in range(6):
                await lost.submit(self.i(u + 1), "FROMAGE")
            self.assertEqual(lost.state, "lost")
            self.show(lost)
        self.run_async(go())

    def test_art(self):
        from halloween.art import motus as art
        from halloween.cogs.motus import score
        rows = [score("GARGOUILLE", "GARGOUILLE")]
        data, seconds = art.flip_gif(rows, 10, "G")
        img = Image.open(BytesIO(data))
        self.assertEqual(img.size, (art.W, art.H))
        self.assertGreater(img.n_frames, 10)


class HiloTest(Base):
    def test_multiplier(self):
        from halloween.cogs.hilo import multiplier
        self.assertIsNone(multiplier(13, True))
        self.assertIsNone(multiplier(1, False))
        self.assertEqual(multiplier(1, True), 1.05)
        self.assertGreater(multiplier(12, True), multiplier(7, True))

    def test_flow(self):
        from halloween.cogs import hilo

        async def go():
            u = 9331
            v = hilo.HiloView(self.bot, self.i(u), True)
            v.current = 3
            self.assertEqual(len(await v.extra_files()), 1)
            self.show(v)
            with mock.patch.object(hilo.random, "randint", lambda a, b: 9):
                await v._guess(True)(self.i(u))
            self.assertEqual((v.streak, v.current), (1, 9))
            self.assertGreater(v.pot, hilo.START_POT)
            self.show(v)
            with mock.patch.object(hilo.random, "randint", lambda a, b: 9):
                await v._guess(False)(self.i(u))  # tie: replay
            self.assertEqual((v.state, v.streak), ("play", 1))
            pot = v.pot
            await v._cash(self.i(u))
            self.assertEqual((v.state, v.reward.candies), ("cashed", pot))
            self.show(v)
            lose = hilo.HiloView(self.bot, self.i(u + 1), True)
            lose.current = 5
            with mock.patch.object(hilo.random, "randint", lambda a, b: 2):
                await lose._guess(True)(self.i(u + 1))
            self.assertEqual((lose.state, lose.reward.candies), ("lost", 0))
            self.show(lose)
        self.run_async(go())


if __name__ == "__main__":
    unittest.main()
