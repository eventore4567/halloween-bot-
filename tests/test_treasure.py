"""La Chasse au trésor du serveur: enigmas, hidden parchment, answers and the podium."""
import asyncio
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween.content import treasure as T


class Perms(SimpleNamespace):
    pass


class FakeChannel:
    def __init__(self, cid, name, public=True):
        self.id, self.name, self.public = cid, name, public
        self.sent = []
        self.mention = f"<#{cid}>"

    def permissions_for(self, who):
        ok = self.public
        return Perms(view_channel=ok, read_message_history=ok, send_messages=True, attach_files=True)

    async def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeGuild:
    def __init__(self, gid, channels):
        self.id = gid
        self.text_channels = channels
        self.me = object()
        self.default_role = object()


class RulesTest(unittest.TestCase):
    def test_hunts_are_solvable(self):
        for seed in range(100):
            h = T.make_hunt(seed)
            self.assertEqual(T.shift(h.cipher_text, -h.cipher_shift), h.answers[0])
            self.assertEqual(sorted(h.anagram), sorted(h.answers[1]))
            self.assertEqual(h.reversed_word[::-1], h.answers[2])
            self.assertEqual(T._count(h.grid, h.answers[3]), 1)
            self.assertEqual((h.answers[3][0], len(h.answers[3])), (h.final_first, h.final_len))
            for w in T.WORDS:  # no other word fits the final clue
                if w != h.answers[3] and w[0] == h.final_first and len(w) == h.final_len:
                    self.assertEqual(T._count(h.grid, w), 0)
        self.assertTrue(T.check(T.make_hunt(1), 0, T.make_hunt(1).answers[0].lower()))
        self.assertEqual(T.normalize("Sorcière !"), "SORCIERE")


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Treasure")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def i(self, uid, guild):
        inter = FakeInteraction(user=FakeUser(uid, f"Chercheur{uid}"), client=self.bot, guild_id=guild.id)
        inter.guild = guild
        return inter

    def test_hunt(self):
        events = FakeChannel(1, "evenements")
        private = FakeChannel(2, "staff", public=False)
        hidden = FakeChannel(3, "general")
        guild = FakeGuild(61, [events, private, hidden])

        async def answer(uid, text):
            inter = self.i(uid, guild)
            await self.cog.tresor.callback(self.cog, inter, text)
            return inter

        async def go():
            with mock.patch.object(self.bot, "get_channel", lambda cid: events), \
                    mock.patch.object(self.cog, "set_status", mock.AsyncMock()), \
                    mock.patch.object(self.mod.scenes, "winner_clip", lambda *a: b"GIF89a"):
                self.assertIsNone(await self.cog.start(guild, events))
                self.assertIsNotNone(await self.cog.start(guild, events))  # one at a time
                self.assertEqual(len(hidden.sent), 1)  # the parchment is in a public channel
                self.assertEqual(private.sent, [])
                st = self.cog.state(61)
                self.assertEqual(st["spot_hint"], ["g", 7])
                hunt = T.make_hunt(st["seed"])
                self.assertIn(hunt.reversed_word, self.cog.status_text())
                for step in range(4):  # every enigma renders
                    p, _files = self.cog.enigma(st, hunt, step)
                    check_layout(self.mod.panel_view(p))
                inter = await answer(501, None)
                self.assertEqual(inter.response.sent[-1][0], "send")
                await answer(501, "mauvais")
                await answer(501, hunt.answers[0])  # too soon after a wrong answer
                self.assertEqual(self.cog.state(61)["progress"].get("501", 0), 0)
                self.cog.wrong.clear()
                for uid in (501, 502, 503, 504):
                    for step in range(4):
                        await answer(uid, hunt.answers[step].lower())
                st = self.cog.state(61)
                self.assertEqual(st["finishers"], [501, 502, 503, 504])
                stats = self.store.stats(61, 501)
                self.assertEqual((stats.get("treasure_win"), stats.get("treasure_steps")), (1, 4))
                self.assertNotIn("treasure_win", self.store.stats(61, 502))
                inter = await answer(501, "encore")
                self.assertIn("déjà trouvé", str(inter.response.sent[-1][1]["view"].to_components()))
                n = len(events.sent)
                self.assertFalse(await self.cog.end(guild))
                self.assertTrue(await self.cog.end(guild, now=time.time() + self.mod.DURATION + 1))
                self.assertIsNone(self.cog.state(61))
                self.assertIsNone(self.cog.status_text())
                self.assertEqual(len(events.sent), n + 1)
                check_layout(events.sent[-1]["view"])
        asyncio.run(go())

    def test_enigma_images(self):
        from halloween.art import treasure as art
        h = T.make_hunt(3)
        for data in (art.cipher_png(h.cipher_text, h.cipher_shift), art.scroll_png(h.anagram),
                     art.grid_png(h.grid, h.final_first, h.final_len)):
            self.assertTrue(data.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
