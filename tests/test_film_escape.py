"""« Le Film de ta Nuit » and the cooperative escape game."""
import asyncio
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.content import escape as X

_real_sleep = asyncio.sleep


async def fast_sleep(delay, *args, **kwargs):
    await _real_sleep(0)


class FilmEscapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def i(self, uid, name="Joueur", **kw):
        return FakeInteraction(user=FakeUser(uid, name), client=self.bot, **kw)

    def show(self, view):
        view.render()
        return check_layout(view)

    def test_film(self):
        from halloween.art.film import film_gif
        from halloween.cogs import film

        u = 9601
        self.store.add_candies(999, u, 777, "t", boost=False)
        self.store.stat_add(999, u, "slots_jackpot", 1)
        info = film.film_info(self.store, 999, FakeUser(u, "Cinéphile"), None)
        self.assertEqual(info["earned"], 777)
        self.assertEqual(info["best"], "Jackpot à la Machine hantée")
        self.assertIsNone(info["pet"])
        data, seconds = film_gif(info, 1)
        img = Image.open(BytesIO(data))
        self.assertGreater(img.n_frames, 50)
        self.assertGreater(seconds, 10)

        async def go():
            inter = self.i(u)
            with mock.patch.object(film, "film_gif", lambda info, seed: (b"GIF", 12.0)):
                await film.Film(self.bot).open(inter)
                self.assertEqual([k for k, _ in inter.response.sent], ["defer", "followup"])
                again = self.i(u)
                await film.Film(self.bot).open(again)  # cooldown
                self.assertNotEqual(again.response.sent[0][0], "defer")
        asyncio.run(go())

    def test_puzzles(self):
        for seed in range(40):
            rooms = X.make_rooms(seed)
            self.assertEqual([r.kind for r in rooms], ["digits", "word", "sum"])
            for r in rooms:
                self.assertEqual(len(r.clues), 4)
            digits, word, vault = rooms
            self.assertRegex(digits.code, r"^[1-9]{4}$")
            self.assertEqual(len(word.code), 5)
            self.assertTrue(int(vault.code) > 0)
        # every fragment is dealt exactly once, whatever the team size
        for n in range(1, 5):
            dealt = [c for seat in range(n) for c in X.deal(["a", "b", "c", "d"], n, seat)]
            self.assertEqual(sorted(dealt), ["a", "b", "c", "d"])
        self.assertEqual(X.normalize(" ombré-1 "), "OMBRE1")

    def test_team_escape(self):
        from halloween.cogs import escape as cog

        async def go():
            host, mate = FakeUser(9611, "Chef"), FakeUser(9612, "Acolyte")
            with mock.patch.object(cog.EscapeView, "later", lambda self, s, fn: None):
                v = cog.EscapeView(self.bot, 999, host, seed=5)
                self.show(v)
                await v._join(FakeInteraction(user=mate, client=self.bot))
                self.assertEqual(len(v.players), 2)
                await v._start(FakeInteraction(user=mate, client=self.bot))  # only the host
                self.assertEqual(v.state, "lobby")
                await v._start(FakeInteraction(user=host, client=self.bot))
                self.assertEqual(v.state, "play")
                self.show(v)
                inter = FakeInteraction(user=mate, client=self.bot)
                await v._clues(inter)
                deadline = v.deadline
                await v.try_code(FakeInteraction(user=host, client=self.bot), "0000")
                self.assertEqual(v.deadline, deadline - cog.PENALTY)
                for _ in range(3):
                    await v.try_code(FakeInteraction(user=host, client=self.bot), v.room.code.lower())
                    self.show(v)
                self.assertEqual(v.state, "won")
                self.assertEqual(self.store.stats(999, mate.id).get("escape_win"), 1)
                self.assertEqual(len(v.lines), 2)
        with mock.patch("asyncio.sleep", fast_sleep):
            asyncio.run(go())

    def test_room_picture(self):
        from halloween.art.escape import room_png
        img = Image.open(BytesIO(room_png(2, "La Porte du Caveau", 3, True, 4)))
        self.assertEqual(img.size, (680, 340))


if __name__ == "__main__":
    unittest.main()
