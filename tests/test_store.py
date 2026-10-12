import unittest

from halloween import config
from halloween.db import NotEnough, Store

G, A, B = 1, 10, 20


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def test_candies_never_go_negative(self):
        self.s.add_candies(G, A, 100, "t")
        with self.assertRaises(NotEnough):
            self.s.spend(G, A, 150, "t")
        self.assertEqual(self.s.candies(G, A), 100)
        self.s.spend(G, A, 100, "t")
        self.assertEqual(self.s.candies(G, A), 0)

    def test_luck_potion_doubles_gains_only(self):
        self.s.add_effect(G, A, "luck", 60)
        self.assertEqual(self.s.add_candies(G, A, 50, "t"), 100)
        self.assertEqual(self.s.add_candies(G, A, 50, "t", boost=False), 50)
        self.s.spend(G, A, 30, "t")
        self.assertEqual(self.s.candies(G, A), 120)

    def test_transfer_is_atomic(self):
        self.s.add_candies(G, A, 40, "t")
        with self.assertRaises(NotEnough):
            self.s.transfer(G, A, B, 50)
        self.s.transfer(G, A, B, 40)
        self.assertEqual((self.s.candies(G, A), self.s.candies(G, B)), (0, 40))

    def test_daily_streak(self):
        self.assertEqual(self.s.claim_daily(G, A, "2026-10-10", "2026-10-09"), 1)
        self.assertIsNone(self.s.claim_daily(G, A, "2026-10-10", "2026-10-09"))
        self.assertEqual(self.s.claim_daily(G, A, "2026-10-11", "2026-10-10"), 2)
        self.assertEqual(self.s.claim_daily(G, A, "2026-10-13", "2026-10-12"), 1)

    def test_daily_limits_and_bonus(self):
        for _ in range(config.LIMITS["memory"]):
            self.assertTrue(self.s.use_play(G, A, "memory"))
        self.assertFalse(self.s.use_play(G, A, "memory"))
        base = self.s.limit_for(G, A, "quiz")
        self.s.bump(G, A, "quiz_bonus", amount=5)
        self.assertEqual(self.s.limit_for(G, A, "quiz"), base + 5)

    def test_cooldown(self):
        self.assertTrue(self.s.take_cooldown(G, A, "wheel", 100))
        self.assertFalse(self.s.take_cooldown(G, A, "wheel", 100))
        self.assertGreater(self.s.cooldown_left(G, A, "wheel"), 90)

    def test_buy_items_and_things(self):
        self.s.add_candies(G, A, 300, "t", boost=False)
        self.s.buy(G, A, 120, item="joker")
        self.assertEqual(self.s.item_qty(G, A, "joker"), 1)
        self.assertTrue(self.s.use_item(G, A, "joker"))
        self.assertFalse(self.s.use_item(G, A, "joker"))
        self.s.buy(G, A, 100, thing="title:x")
        with self.assertRaises(ValueError):
            self.s.buy(G, A, 50, thing="title:x")
        with self.assertRaises(NotEnough):
            self.s.buy(G, A, 1000, item="joker")
        self.assertEqual(self.s.candies(G, A), 80)

    def test_xp_levels(self):
        old, new = self.s.add_xp(G, A, config.xp_for_next(1))
        self.assertEqual((old, new), (1, 2))
        self.s.add_effect(G, A, "wisdom", 60)
        self.s.add_xp(G, A, 10)
        self.assertEqual(self.s.player(G, A)["xp"], config.xp_for_next(1) + 20)

    def test_rank_with_ties(self):
        self.s.add_candies(G, A, 100, "t")
        self.s.add_candies(G, B, 100, "t")
        self.s.add_candies(G, 30, 50, "t")
        self.assertEqual(self.s.rank(G, A, "candies"), (1, 3))
        self.assertEqual(self.s.rank(G, B, "candies"), (1, 3))
        self.assertEqual(self.s.rank(G, 30, "candies"), (3, 3))
        self.assertEqual(self.s.rank(G, 99, "candies"), (None, 3))

    def test_guilds_are_separate(self):
        self.s.add_candies(1, A, 100, "t")
        self.assertEqual(self.s.candies(2, A), 0)

    def test_cards(self):
        self.assertEqual(self.s.add_card(G, A, "c_bat"), 1)
        self.assertEqual(self.s.add_card(G, A, "c_bat"), 2)
        self.assertEqual(self.s.cards(G, A), {"c_bat": 2})

    def test_unlock_once(self):
        self.assertTrue(self.s.unlock(G, A, "ach:x"))
        self.assertFalse(self.s.unlock(G, A, "ach:x"))

    def test_meta_prefix(self):
        self.s.meta_set("duel:1", {"x": 1})
        self.s.meta_set("other", 2)
        self.assertEqual(self.s.meta_prefix("duel:"), {"duel:1": {"x": 1}})
        self.s.meta_del("duel:1")
        self.assertEqual(self.s.meta_prefix("duel:"), {})


if __name__ == "__main__":
    unittest.main()
