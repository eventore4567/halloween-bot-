"""Click through every game like a player would (no Discord connection)."""
import asyncio
import unittest
from unittest import mock

from helpers import FakeInteraction, FakeUser, install_fake_emojis, make_bot

from halloween import config
from halloween.cogs import cards, expedition, formula, hangman, hub, hunt, memory, quiz, shop, wheel

_real_sleep = asyncio.sleep


async def fast_sleep(delay, *args, **kwargs):
    await _real_sleep(0)


class FlowsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def setUp(self):
        self.uid = 500 + self._testMethodName.__hash__() % 1000
        self.user = FakeUser(self.uid, "Joueur")
        self.store.add_candies(999, self.uid, 20_000, "test", boost=False)

    def i(self, **kw):
        return FakeInteraction(user=self.user, client=self.bot, **kw)

    def run_async(self, coro):
        # countdown timers are not under test here: keep them from firing instantly
        with mock.patch("asyncio.sleep", fast_sleep), mock.patch.object(quiz.ShowView, "_arm", lambda *a: None):
            return asyncio.run(coro)

    def test_every_opener_starts(self):
        async def go():
            for key, opener in self.bot.openers.items():
                inter = self.i()
                await opener(inter, edit=False)
                kinds = [k for k, _ in inter.response.sent]
                self.assertTrue(any(k in ("send", "followup") for k in kinds), (key, kinds))
        self.run_async(go())

    def test_hub_select_opens_game_in_place(self):
        async def go():
            v = hub.HubView(self.bot, self.i())
            inter = self.i(data={"values": ["quiz"]}, message=object())
            await v.on_pick(inter)
            self.assertEqual(inter.response.sent[0][0], "edit")
        self.run_async(go())

    def test_show_climb_and_cash(self):
        async def go():
            v = quiz.ShowView(self.bot, self.i())
            before = self.store.candies(999, self.uid)
            await v._start(self.i())
            self.assertEqual(v.state, "question")
            for _ in range(6):
                await v._answer(v.correct)(self.i())
                self.assertEqual(v.state, "answer")
                await v._next(self.i())
            self.assertEqual(v.correct_count, 6)
            await v._ghost(self.i())
            await v._public(self.i())
            self.assertIn("public", v.hint)
            await v._fifty(self.i())
            self.assertEqual(len(v.removed), 2)
            self.assertNotIn(v.correct, v.removed)
            await v._cash(self.i())
            self.assertEqual(v.state, "end")
            self.assertEqual(v.final["amount"], config.SHOW_LADDER[5])
            self.assertGreaterEqual(self.store.candies(999, self.uid) - before, config.SHOW_LADDER[5])
            v.render()
            v.timer and v.timer.cancel()
        self.run_async(go())

    def test_show_fall_to_safe_rung_and_shield(self):
        async def go():
            v = quiz.ShowView(self.bot, self.i())
            await v._start(self.i())
            for _ in range(6):
                await v._answer(v.correct)(self.i())
                await v._next(self.i())
            self.store.give_item(999, self.uid, "shield")
            await v._answer((v.correct + 1) % 4)(self.i())
            self.assertEqual(v.state, "answer")  # the shield saved the run
            await v._next(self.i())
            await v._answer((v.correct + 1) % 4)(self.i())
            self.assertEqual((v.state, v.final["how"]), ("end", "fall"))
            self.assertEqual(v.final["amount"], config.SHOW_LADDER[4])
            v.timer and v.timer.cancel()
        self.run_async(go())

    def test_show_top_of_ladder(self):
        async def go():
            v = quiz.ShowView(self.bot, self.i())
            await v._start(self.i())
            for _ in range(11):
                await v._answer(v.correct)(self.i())
                await v._next(self.i())
            await v._answer(v.correct)(self.i())
            self.assertEqual((v.state, v.final["how"]), ("end", "top"))
            self.assertEqual(self.store.stats(999, self.uid).get("show_top"), 1)
            v.timer and v.timer.cancel()
        self.run_async(go())

    def test_show_daily_limit(self):
        async def go():
            for _ in range(self.store.limit_for(999, self.uid, "quiz")):
                self.assertTrue(self.store.use_play(999, self.uid, "quiz"))
            v = quiz.ShowView(self.bot, self.i())
            await v._start(self.i())
            self.assertEqual(v.state, "empty")
            v.render()
        self.run_async(go())

    def test_memory_win(self):
        async def go():
            v = memory.MemoryView(self.bot, self.i(), True)
            before = self.store.candies(999, self.uid)
            positions = {}
            for idx, sym in enumerate(v.grid):
                positions.setdefault(sym, []).append(idx)
            for a, b in positions.values():
                await v._flip(a)(self.i())
                await v._flip(b)(self.i())
            self.assertEqual(v.state, "won")
            self.assertEqual(v.moves, 8)
            self.assertEqual(v.reward.candies, 240)
            self.assertGreaterEqual(self.store.candies(999, self.uid) - before, 240)
            v.render()
        self.run_async(go())

    def test_memory_mismatch_hides_again(self):
        async def go():
            v = memory.MemoryView(self.bot, self.i(), True)
            a = 0
            b = next(i for i, s in enumerate(v.grid) if s != v.grid[0])
            await v._flip(a)(self.i())
            await v._flip(b)(self.i())
            self.assertEqual(v.open, [])
            self.assertEqual(v.moves, 1)
        self.run_async(go())

    def test_hunt_cash_and_reaper(self):
        async def go():
            v = hunt.HuntView(self.bot, self.i(), True)
            safe = [i for i, c in enumerate(v.board) if c == "ghost"][:3]
            for i in safe:
                await v._dig(i)(self.i())
            pot = v.pot
            self.assertEqual(pot, 12 + 18 + 24)
            before = self.store.candies(999, self.uid)
            await v._cash(self.i())
            self.assertEqual(v.state, "cashed")
            self.assertEqual(v.reward.candies, pot)
            self.assertGreaterEqual(self.store.candies(999, self.uid) - before, pot)
            v2 = hunt.HuntView(self.bot, self.i(), True)
            await v2._dig(v2.board.index("reaper"))(self.i())
            self.assertEqual(v2.state, "dead")
            v2.render()
        self.run_async(go())

    def test_hangman_letters_and_word(self):
        async def go():
            v = hangman.HangmanView(self.bot, self.i(), True)
            v.word, v.hint = "MOMIE", "x"
            for letter in "MOIE":
                await v._letter(self.i(data={"values": [letter]}))
            self.assertEqual(v.state, "won")
            v2 = hangman.HangmanView(self.bot, self.i(), True)
            v2.word = "CHAUVE-SOURIS"
            await v2.full_guess(self.i(), "chauve souris")
            self.assertEqual(v2.state, "won")
            v3 = hangman.HangmanView(self.bot, self.i(), True)
            v3.word = "ZOMBIE"
            for letter in "AKLNPQT":
                await v3._letter(self.i(data={"values": [letter]}))
            self.assertEqual(v3.state, "lost")
        self.run_async(go())

    def test_formula_solve(self):
        async def go():
            v = formula.FormulaView(self.bot, self.i(), True)
            wrong = [k for k in formula.FORMULA_INGREDIENTS if k not in v.secret][:2] + v.secret[:2]
            for k in wrong:
                await v._add(k)(self.i())
            self.assertEqual(len(v.history), 1)
            for k in v.secret:
                await v._add(k)(self.i())
            self.assertEqual(v.state, "won")
            self.assertEqual(v.reward.candies, formula.formula_reward(2))
            self.assertTrue(v.effect)
            v.render()
        self.run_async(go())

    def test_expedition_round_trip(self):
        async def go():
            self.store.add_card(999, self.uid, "l_reaper")
            v = expedition.ExpeditionView(self.bot, self.i())
            await v._team(self.i(data={"values": ["l_reaper"]}))
            await v._pick("castle")(self.i())
            await v._go(self.i())
            trip = v.trip
            self.assertEqual(trip["dest"], "castle")
            self.assertAlmostEqual(trip["chance"], 0.72)
            await v._claim(self.i())  # too early: nothing happens
            self.assertIsNotNone(v.trip)
            trip["ends"] = 0
            self.store.meta_set(f"exp:999:{self.uid}", trip)
            with mock.patch("halloween.cogs.expedition.random.random", lambda: 0.0):
                await v._claim(self.i())
            self.assertIsNone(v.trip)
            self.assertIn("###", v.report)
            self.assertEqual(self.store.stats(999, self.uid).get("exp_win"), 1)
        self.run_async(go())

    def test_wheel_spin_and_cooldown(self):
        async def go():
            v = wheel.WheelView(self.bot, self.i())
            await v._spin(self.i())
            self.assertEqual(v.state, "done")
            self.assertGreater(self.store.cooldown_left(999, self.uid, "wheel"), 0)
            self.store.give_item(999, self.uid, "ticket")
            await v._ticket(self.i())
            self.assertEqual(self.store.item_qty(999, self.uid, "ticket"), 0)
        self.run_async(go())

    def test_cards_booster(self):
        async def go():
            v = cards.CardsView(self.bot, self.i())
            for _ in range(3):
                await v._open(self.i())
            self.assertEqual(sum(self.store.cards(999, self.uid).values()), 3)
            await v._inspect(self.i(data={"values": [next(iter(self.store.cards(999, self.uid)))]}))
            self.assertEqual(v.state, "inspect")
            await v._back(self.i())
        self.run_async(go())

    def test_shop_purchases(self):
        async def go():
            v = shop.ShopView(self.bot, self.i())
            await v._buy(self.i(data={"values": ["item:joker"]}))
            await v._buy(self.i(data={"values": ["item:luck"]}))
            await v._buy(self.i(data={"values": ["title:t_glouton"]}))
            await v._buy(self.i(data={"values": ["theme:purple"]}))
            self.assertEqual(self.store.item_qty(999, self.uid, "joker"), 1)
            self.assertTrue(self.store.effect_active(999, self.uid, "luck"))
            p = self.store.player(999, self.uid)
            self.assertEqual((p["title"], p["theme"]), ("t_glouton", "purple"))
            await v._equip(self.i(data={"values": ["title:"]}))
            self.assertIsNone(self.store.player(999, self.uid)["title"])
        self.run_async(go())

    def test_duel_with_stake(self):
        from halloween.cogs.duel import DuelView

        async def go():
            other = FakeUser(self.uid + 7, "Rival")
            self.store.add_candies(999, other.id, 1000, "t", boost=False)
            v = DuelView(self.bot, self.i(), other, 300)
            v.arm = lambda seconds, token: None  # round timers are not under test here
            await v._accept(FakeInteraction(user=other, client=self.bot))
            self.assertEqual(v.state, "play")
            for _ in range(2):
                await v._play("hunter")(self.i())
                await v._play("vampire")(FakeInteraction(user=other, client=self.bot))
            self.assertTrue(v.clip)
            self.assertEqual(v.state, "over")
            self.assertEqual(v.winner.id, self.uid)
            self.assertEqual(self.store.candies(999, other.id), 700)
            self.assertEqual(self.store.meta_prefix("duel:"), {})
        self.run_async(go())

    def test_events(self):
        from halloween.cogs.drops import BossView, FlashQuizView, LootView

        async def go():
            cog = self.bot.get_cog("Drops")
            loot = LootView(cog, 999)
            await loot._grab(self.i())
            self.assertEqual(loot.winner.id, self.uid)
            fq = FlashQuizView(cog, 999)
            await fq._answer((fq.correct + 1) % 4)(self.i())
            self.assertIn(self.uid, fq.out)
            await fq._answer(fq.correct)(FakeInteraction(user=FakeUser(4242), client=self.bot))
            self.assertEqual(fq.winner.id, 4242)
            boss = BossView(cog, 999, 1)
            boss.hp = 5
            await boss._hit(self.i())
            self.assertTrue(boss.defeated)
            self.assertTrue(boss.rewards)
        self.run_async(go())


if __name__ == "__main__":
    unittest.main()
