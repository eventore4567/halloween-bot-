"""Haunted labyrinth, connect four and the categorised hub."""
import asyncio
import random
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.content import connect4 as C
from halloween.content.maze import N, generate

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


class HubTest(Base):
    def test_categories_cover_openers(self):
        from halloween.cogs import hub
        keys = [k for c in hub.CATEGORIES for k in c[3]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), {g[0] for g in hub.GAMES})
        for k in keys:
            self.assertIn(k, self.bot.openers, k)

        async def go():
            v = hub.HubView(self.bot, self.i(9500))
            self.show(v)
            for key, *_ in hub.CATEGORIES:
                await v.on_category(self.i(9500, data={"values": [key]}))
                self.assertEqual(v.page, "cat:" + key)
                self.show(v)
            await v.toggle(self.i(9500))
            self.assertEqual(v.page, "home")
        self.run_async(go())


class MazeTest(Base):
    def test_generation(self):
        for seed in range(30):
            m = generate(seed)
            dist = m.distances(m.start)
            self.assertEqual(len(dist), N * N)  # every cell reachable
            cells = [m.start, m.exit, m.key, m.ghost, m.candle, *m.candies]
            self.assertEqual(len(cells), len(set(cells)))

    def test_escape_and_capture(self):
        from halloween.cogs import maze as cog

        async def go():
            u = 9511
            v = cog.MazeView(self.bot, self.i(u), True, seed=4)
            self.assertEqual(len(await v.extra_files()), 1)
            self.show(v)
            m = v.maze
            m.ghost = None
            with mock.patch.object(cog, "ghost_move", lambda maze, player, turn, rnd=random: (-5, -5)):
                for target in (m.key, m.exit):
                    while v.player != target and v.state == "play":
                        nxt = m.step_towards(v.player, target)
                        d = next(k for k, (dx, dy) in cog.DIRS.items()
                                 if (v.player[0] + dx, v.player[1] + dy) == nxt)
                        await v._move(d)(self.i(u))
            self.assertEqual(v.state, "escaped")
            self.assertGreaterEqual(v.reward.candies, cog.ESCAPE_REWARD)
            self.show(v)

            w = cog.MazeView(self.bot, self.i(u + 1), True, seed=5)
            first = next(iter(w.maze.neighbours(w.player)))
            w.maze.ghost = first
            d = next(k for k, (dx, dy) in cog.DIRS.items() if (w.player[0] + dx, w.player[1] + dy) == first)
            await w._move(d)(self.i(u + 1))
            self.assertEqual(w.state, "caught")
            self.show(w)
        self.run_async(go())

    def test_picture(self):
        from halloween.art import maze as art
        m = generate(2)
        img = Image.open(BytesIO(art.render(m, m.start, {m.start}, False, 3, 70, 0)))
        self.assertEqual(img.size, (art.W, art.H))


class Connect4Test(Base):
    def test_rules_and_ai(self):
        b = C.new_board()
        for col in (0, 1, 2):
            C.drop(b, col, 1)
        self.assertEqual(C.ai_move(b, 2, blunder=0), 3)  # blocks
        b = C.new_board()
        for col in (0, 1, 2):
            C.drop(b, col, 2)
        C.drop(b, 3, 1)
        for col in (0, 1):
            C.drop(b, col, 1)
        self.assertIsNone(C.winner_cells(b, 2))
        b2 = C.new_board()
        for col in (2, 3, 4):
            C.drop(b2, col, 2)
        col = C.ai_move(b2, 2, blunder=0)  # wins on either side
        C.drop(b2, col, 2)
        self.assertEqual(len(C.winner_cells(b2, 2)), 4)

    def test_vs_witch(self):
        from halloween.cogs import connect4 as cog

        async def go():
            u = 9521
            v = cog.Connect4View(self.bot, self.i(u), True)
            self.show(v)
            with mock.patch.object(cog.C, "ai_move", lambda board, piece=2, **kw: 6), \
                    mock.patch.object(cog.art, "drop_gif", lambda *a: (b"GIF", 0.1)), \
                    mock.patch.object(cog.art, "board_png", lambda *a: b"PNG"):
                for _ in range(4):
                    await v._play(0)(self.i(u))
                    self.show(v)
            self.assertEqual((v.state, v.winner), ("over", 1))
            self.assertEqual(v.reward.candies, cog.WIN_REWARD)
        self.run_async(go())

    def test_pvp_with_stake(self):
        from halloween.cogs import connect4 as cog

        async def go():
            a, b = 9531, 9532
            for uid in (a, b):
                self.store.add_candies(999, uid, 1000, "t", boost=False)
            other = FakeUser(b, "Rival")
            v = cog.Connect4View(self.bot, self.i(a), True, other, 300)
            with mock.patch.object(cog.Connect4View, "_arm_turn", lambda self: None), \
                    mock.patch.object(cog.art, "drop_gif", lambda *a: (b"GIF", 0.1)), \
                    mock.patch.object(cog.art, "board_png", lambda *a: b"PNG"), \
                    mock.patch.object(cog.random, "choice", lambda seq: 1):
                self.show(v)
                await v._accept(FakeInteraction(user=other, client=self.bot))
                self.assertEqual(v.state, "play")
                self.assertEqual(self.store.candies(999, a), 700)
                await v._play(1)(FakeInteraction(user=other, client=self.bot))  # not their turn
                self.assertEqual(v.turn, 1)
                for _ in range(3):
                    await v._play(0)(self.i(a))
                    await v._play(1)(FakeInteraction(user=other, client=self.bot))
                    self.show(v)
                await v._play(0)(self.i(a))
            self.assertEqual((v.state, v.winner), ("over", 1))
            self.assertGreaterEqual(self.store.candies(999, a), 1300)
            self.assertEqual(self.store.candies(999, b), 700)
            self.show(v)
        self.run_async(go())

    def test_drop_gif(self):
        from halloween.art import connect4 as art
        b = C.new_board()
        before = [r[:] for r in b]
        row = C.drop(b, 3, 1)
        data, seconds = art.drop_gif(before, [(row, 3, 1)], None)
        self.assertGreater(Image.open(BytesIO(data)).n_frames, 5)


if __name__ == "__main__":
    unittest.main()
