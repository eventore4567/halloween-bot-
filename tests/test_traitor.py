"""Le Traître: rules, and a whole simulated game through the Discord view."""
import asyncio
import random
import sys
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.content import traitor as T


def stub(*args, **kwargs):
    return b"GIF89a"


class RulesTest(unittest.TestCase):
    def test_deal(self):
        for n in range(T.MIN_PLAYERS, T.MAX_PLAYERS + 1):
            roles = T.deal(n, random.Random(n))
            self.assertEqual(len(roles), n)
            self.assertEqual(roles.count("vampire"), T.vampire_count(n))
            self.assertEqual(roles.count("medium"), 1)
            self.assertEqual(roles.count("guardian"), 1 if n >= 5 else 0)
            g = T.Game.start(list(range(1, n + 1)), random.Random(n))
            self.assertIsNone(g.winner())  # nobody wins before the first night

    def _game(self, roles):
        g = T.Game(list(roles))
        g.roles = dict(roles)
        g.alive = list(roles)
        return g

    def test_night_guard_and_medium(self):
        g = self._game({1: "vampire", 2: "medium", 3: "guardian", 4: "villager", 5: "villager"})
        g.begin_night()
        self.assertEqual(sorted(g.pending_night()), [1, 2, 3])
        with self.assertRaises(ValueError):
            g.act(1, 1)  # a vampire cannot bite a vampire
        g.act(1, 4)
        self.assertEqual(g.act(2, 1), "vampire")
        with self.assertRaises(ValueError):
            g.act(2, 4)  # one vision per night
        g.act(3, 4)
        self.assertEqual(g.pending_night(), [])
        self.assertEqual(g.resolve_night(), (4, True))  # saved
        self.assertIn(4, g.alive)
        g.begin_night()
        self.assertNotIn(4, g.targets(3))  # never the same twice in a row
        g.act(1, 5)
        g.act(3, 3)
        self.assertEqual(g.resolve_night(), (5, False))
        self.assertNotIn(5, g.alive)

    def test_votes_and_winners(self):
        g = self._game({1: "vampire", 2: "medium", 3: "villager", 4: "villager"})
        g.begin_vote()
        g.vote(1, 3)
        g.vote(2, 1)
        g.vote(3, 1)
        g.vote(4, 3)
        self.assertTrue(g.all_voted())
        self.assertIsNone(g.resolve_vote())  # tie: nobody
        g.begin_vote()
        for v, t in ((1, 3), (2, 1), (3, 1), (4, T.SKIP)):
            g.vote(v, t)
        self.assertEqual(g.resolve_vote(), 1)
        self.assertEqual(g.winner(), "village")
        g = self._game({1: "vampire", 2: "villager", 3: "villager"})
        g.alive.remove(3)
        self.assertEqual(g.winner(), "vampires")
        g = self._game({1: "vampire", 2: "villager", 3: "villager", 4: "villager"})
        g.begin_vote()
        for v, t in ((1, 2), (2, T.SKIP), (3, T.SKIP), (4, 2)):
            g.vote(v, t)
        self.assertIsNone(g.resolve_vote())  # as many skips as votes: nobody
        g.begin_night()
        self.assertIn(g.resolve_night(random.Random(1))[0], (2, 3, 4))  # asleep vampires still bite


class ScenesTest(unittest.TestCase):
    def test_scenes(self):
        from halloween.art import traitor as art
        for data in (art.night_gif(1, 1), art.dawn_gif("A", None, False, 1, 1), art.dawn_gif("B", None, True, 2, 1),
                     art.dawn_gif(None, None, False, 3, 1),
                     art.banish_gif("C", None, "Médium", "crystal", False, 1),
                     art.end_gif("vampires", [("D", None, "vampire"), ("E", None, "vampire")], 1),
                     art.end_gif("village", [(f"V{k}", None, "pumpkin") for k in range(9)], 1)):
            gif = Image.open(BytesIO(data))
            self.assertEqual(gif.size, (art.W, art.H))
            self.assertGreater(gif.n_frames, 10)


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Traitor")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def i(self, user, **kw):
        return FakeInteraction(user=user, client=self.bot, **kw)

    def test_full_game(self):
        mod = self.mod
        users = [FakeUser(8800 + k, f"Joueur{k}") for k in range(5)]

        async def go():
            with mock.patch.object(mod.art, "night_gif", stub), mock.patch.object(mod.art, "dawn_gif", stub), \
                    mock.patch.object(mod.art, "banish_gif", stub), mock.patch.object(mod.art, "end_gif", stub), \
                    mock.patch.object(mod.TraitorView, "later", lambda self, s, fn: None):
                v = mod.TraitorView(self.bot, 999, None, users[0])
                check_layout(v)
                await v._start(self.i(users[0]))  # not enough players yet
                self.assertEqual(v.state, "lobby")
                for u in users[1:]:
                    await v._join(self.i(u))
                await v._join(self.i(users[1]))  # twice: refused
                self.assertEqual(len(v.order), 5)
                await v._start(self.i(users[1]))  # only the host starts
                self.assertEqual(v.state, "lobby")
                await v._start(self.i(users[0]))
                self.assertEqual(v.state, "night")
                check_layout(v)
                g = v.game
                by_uid = {u.id: u for u in users}
                for u in users:  # everybody can read their role
                    inter = self.i(u)
                    await v._my_role(inter)
                    self.assertEqual(inter.response.sent[-1][0], "send")
                vampires = g.vampires()
                rounds = 0
                while v.state != "over" and rounds < 6:
                    rounds += 1
                    self.assertEqual(v.state, "night")
                    for uid in list(g.pending_night()):
                        inter = self.i(by_uid[uid])
                        await v._act(inter)
                        pick = inter.response.sent[-1][1]["view"]
                        check_layout(pick)
                        role = g.role(uid)
                        target = uid if role == "guardian" and uid in g.targets(uid) else g.targets(uid)[0]
                        await pick._pick(self.i(by_uid[uid], data={"values": [str(target)]}))
                    if v.state == "over":
                        break
                    self.assertEqual(v.state, "day")
                    check_layout(v)
                    for uid in list(g.alive):
                        await v._ready(self.i(by_uid[uid]))
                        if v.state != "day":
                            break
                    self.assertEqual(v.state, "vote")
                    check_layout(v)
                    suspect = next(x for x in g.alive if x in vampires)
                    for uid in list(g.alive):
                        await v._vote(self.i(by_uid[uid], data={"values": [str(suspect)]}))
                    if v.state == "verdict":
                        check_layout(v)
                        if v.ending:  # the decisive banishment is shown first, then the winners
                            await v.finish(prefix=v.flash)
                        else:
                            await v.start_night()
                self.assertEqual(v.state, "over")
                self.assertEqual(g.winner(), "village")
                check_layout(v)
                for uid in g.players:
                    won = g.team(uid) == "village"
                    self.assertEqual(self.store.stats(999, uid).get("traitor_win", 0), 1 if won else 0)
        asyncio.run(go())

    def test_night_deadline_counts_from_the_scene(self):
        mod = self.mod
        users = [FakeUser(8700 + k, f"J{k}") for k in range(4)]

        async def slow_scene(self_, kind, make, *args):
            await asyncio.sleep(0)
            mod.time.time = lambda base=mod.time.time(): base + 30  # rendering took 30 s
            return None

        async def go():
            real = mod.time.time
            try:
                with mock.patch.object(mod.TraitorView, "later", lambda self, s, fn: None), \
                        mock.patch.object(mod.TraitorView, "scene", slow_scene):
                    v = mod.TraitorView(self.bot, 999, None, users[0])
                    for u in users[1:]:
                        await v._join(self.i(u))
                    start = real()
                    await v._start(self.i(users[0]))
                    self.assertGreaterEqual(v.deadline - start, mod.NIGHT_TIME + 29)
            finally:
                mod.time.time = real
        asyncio.run(go())

    def test_big_game_summary_fits(self):
        mod = self.mod
        users = [FakeUser(8600 + k, f"Un nom de joueur assez long {k}") for k in range(12)]

        async def go():
            with mock.patch.object(mod.TraitorView, "later", lambda self, s, fn: None), \
                    mock.patch.object(mod.art, "end_gif", stub), mock.patch.object(mod.art, "night_gif", stub):
                v = mod.TraitorView(self.bot, 998, None, users[0])
                for u in users[1:]:
                    await v._join(self.i(u))
                await v._start(self.i(users[0]))
                g = v.game
                for x in g.vampires():
                    g.alive.remove(x)
                long_line = "x" * 400
                with mock.patch.object(mod, "grant", lambda *a, **k: mock.Mock(
                        line=lambda: long_line, candies=10, leveled=True, new_level=5, achievements=[1])):
                    await v.finish()
                check_layout(v)
        asyncio.run(go())

    def test_traitor_counts_as_a_game(self):
        from halloween import challenges
        self.assertIn("traitre", challenges.GAME_REASONS)

    def test_lobby_cancelled_without_players(self):
        mod = self.mod

        async def go():
            with mock.patch.object(mod.TraitorView, "later", lambda self, s, fn: None):
                v = mod.TraitorView(self.bot, 999, None, FakeUser(8900, "Seul"))
                await v.lobby_timeout()
                self.assertEqual(v.state, "over")
                check_layout(v)
        asyncio.run(go())

    def test_open_from_command(self):
        async def go():
            with mock.patch.object(self.mod.TraitorView, "later", lambda self, s, fn: None):
                inter = self.i(FakeUser(8950, "Hôte"))
                await self.cog.open(inter)
                self.assertEqual(inter.response.sent[-1][0], "send")
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
