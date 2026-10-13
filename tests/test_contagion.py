"""La Malédiction contagieuse: a curse passed on by mentioning someone in the chat."""
import asyncio
import datetime as dt
import sys
import time
import unittest
from io import BytesIO
from unittest import mock

from helpers import FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween import config
from halloween.rewards import grant


class FakeChannel:
    def __init__(self):
        self.id = 4242
        self.sent = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)


class FakeGuild:
    def __init__(self, gid, members):
        self.id = gid
        self.members = {m.id: m for m in members}

    def get_member(self, uid):
        return self.members.get(uid)


class FakeMessage:
    def __init__(self, guild, author, mentions):
        self.guild, self.author, self.mentions = guild, author, mentions
        self.reactions = []

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)


class ContagionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Contagion")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def setup_guild(self, gid, n):
        users = [FakeUser(gid * 100 + k, f"Joueur{k}") for k in range(n)]
        for u in users:
            grant(self.store, gid, u.id, 1000, 0, "test")
        return FakeGuild(gid, users), users

    def test_scenes(self):
        art = self.mod.art
        people = [(f"P{k}", None) for k in range(5)]
        for data in (art.pass_gif(people, 1), art.final_gif(people, False, 1), art.final_gif(people, True, 1)):
            self.assertGreater(Image.open(BytesIO(data)).n_frames, 10)
        self.assertEqual(Image.open(BytesIO(art.map_png(people[:1], 40))).size, (art.W, art.H))

    def test_chain_and_expiry(self):
        guild, users = self.setup_guild(71, 4)
        stranger = FakeUser(7199, "Jamais joué")
        guild.members[stranger.id] = stranger
        channel = FakeChannel()

        async def go():
            self.assertTrue(await self.cog.start(guild, users[0], channel))
            self.assertFalse(await self.cog.start(guild, users[1], channel))  # one curse at a time
            check_layout(channel.sent[-1]["view"])
            # someone else mentioning: nothing happens
            await self.cog.on_message(FakeMessage(guild, users[2], [users[3]]))
            self.assertEqual(self.cog.state(71)["holder"], users[0].id)
            # a member who never played cannot catch it
            await self.cog.on_message(FakeMessage(guild, users[0], [stranger]))
            self.assertEqual(self.cog.state(71)["holder"], users[0].id)
            msg = FakeMessage(guild, users[0], [users[1]])
            await self.cog.on_message(msg)
            self.assertEqual(msg.reactions, ["💀"])
            st = self.cog.state(71)
            self.assertEqual((st["holder"], st["chain"]), (users[1].id, [users[0].id, users[1].id]))
            check_layout(channel.sent[-1]["view"])
            # cannot go back to someone who already had it
            await self.cog.on_message(FakeMessage(guild, users[1], [users[0]]))
            self.assertEqual(self.cog.state(71)["holder"], users[1].id)
            await self.cog.on_message(FakeMessage(guild, users[1], [users[2]]))
            before = {u.id: self.store.candies(71, u.id) for u in users}
            self.assertFalse(await self.cog.expire(guild))  # not yet
            self.assertTrue(await self.cog.expire(guild, now=time.time() + self.mod.HOLD_TIME + 5))
            self.assertIsNone(self.cog.state(71))
            loser = users[2].id
            self.assertEqual(before[loser] - self.store.candies(71, loser), self.mod.penalty(before[loser]))
            for u in users[:2]:
                self.assertGreater(self.store.candies(71, u.id), before[u.id])
            self.assertEqual(self.store.candies(71, users[3].id), before[users[3].id])  # never in the chain
            check_layout(channel.sent[-1]["view"])
        with mock.patch.object(self.bot, "get_channel", lambda cid: channel):
            asyncio.run(go())

    def test_chain_breaks_at_max(self):
        n = self.mod.MAX_CHAIN
        guild, users = self.setup_guild(72, n)
        channel = FakeChannel()

        async def go():
            await self.cog.start(guild, users[0], channel)
            before = self.store.candies(72, users[-1].id)
            with mock.patch.object(self.mod.art, "pass_gif", lambda *a: b"GIF89a"):
                for a, b in zip(users, users[1:]):
                    await self.cog.on_message(FakeMessage(guild, a, [b]))
            self.assertIsNone(self.cog.state(72))
            self.assertGreater(self.store.candies(72, users[-1].id), before)  # even the last one wins
            self.assertIn("brisée", str(channel.sent[-1]["view"].to_components()))
        with mock.patch.object(self.bot, "get_channel", lambda cid: channel):
            asyncio.run(go())

    def test_daily_strike(self):
        guild, users = self.setup_guild(73, 4)
        channel = FakeChannel()
        self.store.guild_set(73, drop_channel=channel.id, drops_on=1)
        drops = self.bot.get_cog("Drops")
        day = "2026-10-20"
        hour = self.mod.strike_hour(73, day)

        async def go():
            early = dt.datetime(2026, 10, 20, hour - 1, 0, tzinfo=config.TZ)
            late = dt.datetime(2026, 10, 20, hour, 5, tzinfo=config.TZ)
            drops.authors[73] = {users[0].id: time.time()}
            self.assertFalse(await self.cog.maybe_strike(guild, late))  # server too quiet
            drops.authors[73] = {u.id: time.time() for u in users}
            self.assertFalse(await self.cog.maybe_strike(guild, early))
            self.assertTrue(await self.cog.maybe_strike(guild, late))
            self.assertIn(self.cog.state(73)["holder"], [u.id for u in users])
            self.store.meta_del("contagion:73")
            self.assertFalse(await self.cog.maybe_strike(guild, late))  # once a day
        with mock.patch.object(self.bot, "get_channel", lambda cid: channel):
            asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
