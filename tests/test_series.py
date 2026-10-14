"""La Série hantée: nightly episodes, server votes, four endings, a new cast each season."""
import asyncio
import datetime as dt
import re
import sys
import unittest
from unittest import mock

from types import SimpleNamespace

import discord
from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween import config
from halloween.content import series as S
from halloween.rewards import grant


class FakeChannel:
    def __init__(self):
        self.id = 777
        self.sent = []
        self.fail = False

    async def send(self, content=None, **kwargs):
        if self.fail:
            raise discord.HTTPException(SimpleNamespace(status=500, reason="Server Error"), "boom")
        self.sent.append(dict(kwargs, content=content))


class FakeMember(FakeUser):
    pass


class FakeGuild:
    def __init__(self, gid, members):
        self.id = gid
        self.members = {m.id: m for m in members}

    def get_member(self, uid):
        return self.members.get(uid)


class ContentTest(unittest.TestCase):
    def test_story(self):
        cast = {"hero": "H", "suspect": "S", "victim": "V"}
        self.assertEqual(len(S.EPISODES[-1].choices), 0)  # the finale
        for ep in S.EPISODES[:-1]:
            S.fill(ep.text, cast)
            self.assertEqual(len(ep.choices), 3)
            for c in ep.choices:
                self.assertIn(c.leaning, S.LEANINGS)
                S.fill(c.label, cast)
                S.fill(c.outcome, cast)
                self.assertLessEqual(len(S.fill(c.label, {k: "X" * 32 for k in cast})), 80 + 40)
        for title, text in S.ENDINGS.values():
            S.fill(text, cast)
        self.assertEqual(S.ending({}), "courage")
        self.assertEqual(S.ending({"lumiere": 2, "savoir": 2}), "lumiere")
        self.assertEqual(S.ending({"soupcon": 3, "savoir": 2}), "soupcon")


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Series")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def test_season(self):
        mod = self.mod
        members = [FakeMember(6600 + k, f"Acteur{k}") for k in range(5)]
        for m in members:
            grant(self.store, 66, m.id, 500 + m.id, 0, "test")
        guild = FakeGuild(66, members)
        channel = FakeChannel()

        async def go():
            with mock.patch.object(mod.art, "episode_gif", lambda *a: b"GIF89a"):
                self.assertFalse(await self.cog.release(guild))  # no events channel yet
                self.assertTrue(await self.cog.release(guild, channel))
                st = self.cog.state(66)
                self.assertEqual((st["season"], st["ep"]), (1, 0))
                self.assertTrue(all(uid in guild.members for uid, _ in st["cast"]))
                self.assertIn("vous êtes dans la série", channel.sent[1]["content"])  # the cast is pinged once
                for ep in range(len(S.EPISODES) - 1):
                    view = next(m["view"] for m in reversed(channel.sent) if m.get("view"))
                    check_layout(view)
                    ids = re.findall(r"nh:sv:\d+:\d+:\d", str(view.to_components()))
                    self.assertEqual(len(ids), 3)
                    # two members vote for the "savoir"-leaning choice when there is one, one for another
                    k = next((i for i, c in enumerate(S.EPISODES[ep].choices) if c.leaning == "savoir"), 0)
                    for m in members[:2]:
                        inter = FakeInteraction(user=m, client=self.bot, guild_id=66)
                        inter.guild = guild
                        await self.cog.vote(inter, 1, ep, k)
                    inter = FakeInteraction(user=members[2], client=self.bot, guild_id=66)
                    inter.guild = guild
                    await self.cog.vote(inter, 1, ep, (k + 1) % 3)
                    await self.cog.vote(inter, 1, ep, (k + 1) % 3)  # voting twice pays once
                    late = FakeInteraction(user=members[3], client=self.bot, guild_id=66)
                    late.guild = guild
                    await self.cog.vote(late, 1, ep + 1, 0)  # a vote for the wrong episode is refused
                    await self.cog.release(guild, channel)
                    last = next(m["view"] for m in reversed(channel.sent) if m.get("view"))
                    self.assertIn("Précédemment", str(last.to_components()))
                st = self.cog.state(66)
                self.assertEqual(st["ep"], len(S.EPISODES) - 1)
                self.assertEqual(S.ending(st["totals"]), "savoir")
                last = next(m["view"] for m in reversed(channel.sent) if m.get("view"))
                self.assertIn(S.ENDINGS["savoir"][0], str(last.to_components()))
                self.assertEqual(self.store.stats(66, members[2].id)["series_votes"], len(S.EPISODES) - 1)
                await self.cog.release(guild, channel)  # a new season
                st = self.cog.state(66)
                self.assertEqual((st["season"], st["ep"], st["totals"]), (2, 0, {}))
        asyncio.run(go())

    def test_failed_send_retries_the_same_episode(self):
        mod = self.mod
        guild = FakeGuild(69, [])
        channel = FakeChannel()

        async def go():
            with mock.patch.object(mod.art, "episode_gif", lambda *a: b"GIF89a"):
                await self.cog.release(guild, channel)
                channel.fail = True
                self.assertFalse(await self.cog.release(guild, channel))
                self.assertEqual(self.cog.state(69)["ep"], 0)  # nothing skipped
                channel.fail = False
                self.assertTrue(await self.cog.release(guild, channel))
                self.assertEqual(self.cog.state(69)["ep"], 1)
        asyncio.run(go())

    def test_cast_falls_back_to_extras(self):
        guild = FakeGuild(67, [])
        cast = asyncio.run(self.cog.pick_cast(guild))
        self.assertEqual([uid for uid, _ in cast], [None, None, None])
        self.assertEqual(self.cog.names(guild, dict(cast=cast))["hero"], self.mod.EXTRAS[0])

    def test_cast_fetches_uncached_members(self):
        """Without the members intent the cache is empty: the cast is fetched from Discord."""
        members = [FakeMember(6500 + k, f"Absent{k}") for k in range(4)]
        for m in members:
            grant(self.store, 65, m.id, 300, 0, "test")

        class NoCacheGuild(FakeGuild):
            def get_member(self, uid):
                return None

            async def fetch_member(self, uid):
                return self.members[uid]

        guild = NoCacheGuild(65, members)
        cast = asyncio.run(self.cog.pick_cast(guild))
        self.assertEqual(len([uid for uid, _ in cast if uid]), 3)

    def test_nightly_release(self):
        mod = self.mod
        guild = FakeGuild(68, [])
        channel = FakeChannel()
        self.store.guild_set(68, drop_channel=channel.id)

        async def go():
            with mock.patch.object(mod.art, "episode_gif", lambda *a: b"GIF89a"), \
                    mock.patch.object(self.bot, "get_channel", lambda cid: channel):
                early = dt.datetime(2026, 10, 20, mod.RELEASE_HOUR - 1, 30, tzinfo=config.TZ)
                late = dt.datetime(2026, 10, 20, mod.RELEASE_HOUR, 2, tzinfo=config.TZ)
                self.assertFalse(await self.cog.maybe_release(guild, early))
                self.assertTrue(await self.cog.maybe_release(guild, late))
                self.assertFalse(await self.cog.maybe_release(guild, late))  # once a night
                nxt = late + dt.timedelta(days=1)
                self.assertTrue(await self.cog.maybe_release(guild, nxt))
                self.assertEqual(self.cog.state(68)["ep"], 1)
        asyncio.run(go())

    def test_vote_button_survives_restart(self):
        mod = self.mod
        item = mod.SeriesVote(3, 4, 2, "Choix", "book")
        match = re.fullmatch(mod.SeriesVote.__discord_ui_compiled_template__, item.item.custom_id)

        async def go():
            inst = await mod.SeriesVote.from_custom_id(None, item.item, match)
            self.assertEqual((inst.season, inst.ep, inst.k), (3, 4, 2))
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
