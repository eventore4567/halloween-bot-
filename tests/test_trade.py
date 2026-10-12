"""Card trading between members, and the winner clips of server events."""
import asyncio
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.content.games import CARDS

_real_sleep = asyncio.sleep


async def fast_sleep(delay, *args, **kwargs):
    await _real_sleep(0)


KEYS = [c["key"] for c in CARDS]


class TradeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def test_store_trade_is_all_or_nothing(self):
        g, a, b = 999, 9801, 9802
        self.store.add_card(g, a, KEYS[0])
        self.store.add_card(g, a, KEYS[1])
        self.store.add_card(g, b, KEYS[5])
        self.store.add_candies(g, a, 300, "t", boost=False)
        # b does not own KEYS[6]: nothing moves
        self.assertFalse(self.store.trade(g, a, b, [KEYS[0]], [KEYS[6]], 0))
        self.assertEqual(self.store.cards(g, a).get(KEYS[0]), 1)
        # not enough candies: nothing moves
        self.assertFalse(self.store.trade(g, a, b, [KEYS[0]], [KEYS[5]], 10**6))
        self.assertEqual(self.store.cards(g, b).get(KEYS[5]), 1)
        self.assertTrue(self.store.trade(g, a, b, [KEYS[0], KEYS[1]], [KEYS[5]], 100))
        self.assertEqual(set(self.store.cards(g, a)), {KEYS[5]})
        self.assertEqual(set(self.store.cards(g, b)), {KEYS[0], KEYS[1]})
        self.assertEqual(self.store.candies(g, a), 200)
        # the same card twice needs two copies
        self.assertFalse(self.store.trade(g, b, a, [KEYS[0], KEYS[0]], [], 0))

    def test_trade_flow(self):
        from halloween.cogs import trade

        async def go():
            a, b = FakeUser(9811, "Alpha"), FakeUser(9812, "Bravo")
            for k in KEYS[:3]:
                self.store.add_card(999, a.id, k)
            self.store.add_card(999, b.id, KEYS[-1])
            with mock.patch.object(trade.art, "trade_gif", lambda *a, **k: b"GIF"):
                v = trade.TradeView(self.bot, 999, a, b, 0)
                check_layout(v)
                await v._pick_give(FakeInteraction(user=b, client=self.bot, data={"values": [KEYS[0]]}))
                self.assertEqual(v.give, [])  # only the proposer chooses
                await v._pick_give(FakeInteraction(user=a, client=self.bot, data={"values": KEYS[:2]}))
                await v._pick_take(FakeInteraction(user=a, client=self.bot, data={"values": [KEYS[-1]]}))
                self.assertEqual((v.give, v.take), (KEYS[:2], [KEYS[-1]]))
                await v._propose(FakeInteraction(user=a, client=self.bot))
                self.assertEqual(v.state, "offer")
                check_layout(v)
                await v._accept(FakeInteraction(user=a, client=self.bot))  # the proposer cannot accept
                self.assertEqual(v.state, "offer")
                await v._accept(FakeInteraction(user=b, client=self.bot))
                self.assertEqual(v.state, "done")
                check_layout(v)
            self.assertIn(KEYS[-1], self.store.cards(999, a.id))
            self.assertIn(KEYS[0], self.store.cards(999, b.id))
            self.assertEqual(self.store.stats(999, b.id).get("trades"), 1)
        asyncio.run(go())

    def test_trade_xp_is_capped_and_completion_paid_once(self):
        from halloween.cogs import trade
        from halloween.content.games import COLLECTION_BONUS

        async def go():
            a, b = FakeUser(9831, "Collector"), FakeUser(9832, "Friend")
            for k in KEYS[:-1]:
                self.store.add_card(999, a.id, k)
            self.store.add_card(999, a.id, KEYS[0])  # a spare copy to give away
            self.store.add_card(999, b.id, KEYS[-1])

            async def deal(src, dst, give, take=()):
                v = trade.TradeView(self.bot, 999, src, dst, 0)
                v.give, v.take, v.state = list(give), list(take), "offer"
                await v._accept(FakeInteraction(user=dst, client=self.bot))
                self.assertEqual(v.state, "done")

            with mock.patch.object(trade.art, "trade_gif", lambda *x, **k: b"GIF"):
                before = self.store.candies(999, a.id)
                await deal(a, b, [KEYS[0]], [KEYS[-1]])  # a completes the set through a trade
                self.assertEqual(len(self.store.cards(999, a.id)), len(KEYS))
                gained = self.store.candies(999, a.id) - before  # bonus (+ the "all cards" achievement)
                self.assertTrue(COLLECTION_BONUS <= gained < 2 * COLLECTION_BONUS, gained)
                await deal(a, b, [KEYS[-1]])  # gives it back…
                before = self.store.candies(999, a.id)
                await deal(b, a, [KEYS[-1]])  # …and completes again: not paid twice
                self.assertLess(self.store.candies(999, a.id) - before, COLLECTION_BONUS)  # (an achievement may pay)
                xp_before = self.store.player(999, b.id)["xp"]
                for _ in range(5):  # trading the same card back and forth
                    await deal(a, b, [KEYS[-1]])
                    await deal(b, a, [KEYS[-1]])
                gained = self.store.player(999, b.id)["xp"] - xp_before
                self.assertLessEqual(gained, 10 * trade.XP_TRADES_PER_DAY)
        asyncio.run(go())

    def test_pictures(self):
        from halloween.art import trade as art
        self.assertTrue(art.offer_png("A", "B", KEYS[:3], [KEYS[-1]], 50).startswith(b"\x89PNG"))
        self.assertGreater(Image.open(BytesIO(art.trade_gif("A", "B", KEYS[:1], KEYS[-2:], 0, 1))).n_frames, 10)


class WinnerClipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()

    def test_loot_winner_scene(self):
        from halloween.cogs.drops import LootView
        from halloween.ui import SCENE

        async def go():
            cog = self.bot.get_cog("Drops")
            loot = LootView(cog, 999)
            pushed = []

            async def push(interaction=None, attachments=None):
                loot.render()
                pushed.append(attachments)
            loot.push = push
            await loot._grab(FakeInteraction(user=FakeUser(9821, "Tomioka"), client=self.bot))
            self.assertEqual(loot.winner.id, 9821)
            self.assertEqual([f.filename for f in pushed[-1]], [SCENE])
            urls = [it.media.url for c in loot.walk_children() if c.__class__.__name__ == "MediaGallery"
                    for it in c.items]
            self.assertEqual(urls, [f"attachment://{SCENE}"])
            check_layout(loot)
        with mock.patch("asyncio.sleep", fast_sleep):
            asyncio.run(go())

    def test_winner_clip(self):
        from halloween.art import neon, scenes
        data = scenes.winner_clip("Tomioka", "TOMIOKA A ÉTÉ LE PLUS RAPIDE !", "+209 BONBONS", "candy_bag",
                                  neon.ORANGE, None, 1)
        self.assertGreater(Image.open(BytesIO(data)).n_frames, 15)


if __name__ == "__main__":
    unittest.main()
