"""Opt-in daily reminder for the October calendar and the daily chest."""
import asyncio
import datetime as dt
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import discord
from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween import config
from halloween.cogs import reminder as R


class FakeChannel:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send(self, **kwargs):
        if self.fail:
            raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "missing access")
        self.sent.append(kwargs)


class FakeGuild:
    """A guild where every user is still a member, except ``gone``."""

    def __init__(self, gone=()):
        self.name = "Serveur test"
        self.gone = set(gone)

    def get_member(self, uid):
        return None if uid in self.gone else object()

    async def fetch_member(self, uid):
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "unknown member")


class ReminderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store

    def test_toggle_and_pending(self):
        g = 4242
        self.assertTrue(R.toggle(self.store, g, 1))
        self.assertTrue(R.toggle(self.store, g, 2))
        self.assertFalse(R.toggle(self.store, g, 2))
        self.assertEqual(R.subscribers(self.store, g), [1])
        oct14 = dt.datetime(2026, 10, 14, 19, 0, tzinfo=config.TZ)
        self.assertEqual(R.pending(self.store, g, oct14), [(1, ["calendar", "daily"])])
        self.store.unlock(g, 1, "cal:2026-14")
        self.assertEqual(R.pending(self.store, g, oct14), [(1, ["daily"])])
        nov = dt.datetime(2026, 11, 2, 19, 0, tzinfo=config.TZ)
        self.assertEqual(R.pending(self.store, g, nov), [(1, ["daily"])])

    def test_layouts(self):
        for day, todo, server in ((14, ("calendar", "daily"), None), (31, ("calendar",), None),
                                  (None, ("daily",), None), (14, ("daily",), "Mon serveur")):
            view = R.reminder_view(day, todo, [1, 2, 3], server)
            check_layout(view)

    def test_sends_once_a_day_after_the_hour(self):
        g = 4343
        cog = self.bot.get_cog("Reminder")
        R.toggle(self.store, g, 77)
        channel = FakeChannel()
        self.store.guild_set(g, drop_channel=555)

        async def go():
            with mock.patch.object(self.bot, "get_channel", lambda cid: channel if cid == 555 else None), \
                    mock.patch.object(self.bot, "get_guild", lambda gid: FakeGuild()):
                early = dt.datetime(2026, 10, 14, 17, 59, tzinfo=config.TZ)
                self.assertEqual(await cog.maybe_remind(g, early), 0)
                late = dt.datetime(2026, 10, 14, 18, 1, tzinfo=config.TZ)
                self.assertEqual(await cog.maybe_remind(g, late), 1)
                self.assertEqual(await cog.maybe_remind(g, late), 0)  # once a day
            self.assertEqual(len(channel.sent), 1)
            mentions = channel.sent[0]["allowed_mentions"]
            self.assertEqual([u.id for u in mentions.users], [77])
        asyncio.run(go())

    def test_private_message_without_channel(self):
        g = 4444
        cog = self.bot.get_cog("Reminder")
        R.toggle(self.store, g, 88)
        got = []

        async def send(**kwargs):
            got.append(kwargs)

        async def go():
            user = SimpleNamespace(send=send)
            with mock.patch.object(self.bot, "get_channel", lambda cid: None), \
                    mock.patch.object(self.bot, "get_user", lambda uid: user), \
                    mock.patch.object(self.bot, "get_guild", lambda gid: FakeGuild()):
                now = dt.datetime(2026, 10, 20, 21, 0, tzinfo=config.TZ)
                self.assertEqual(await cog.maybe_remind(g, now), 1)
            self.assertEqual(len(got), 1)
            self.assertIsInstance(got[0]["view"], discord.ui.LayoutView)
        asyncio.run(go())

    def test_groups_failures_and_departures(self):
        g = 4545
        cog = self.bot.get_cog("Reminder")
        for u in (11, 12, 13):
            R.toggle(self.store, g, u)
        self.store.unlock(g, 11, "cal:2026-15")  # 11: only the daily chest left
        self.store.claim_daily(g, 12, "2026-10-15", "2026-10-14")  # 12: only the calendar box left
        self.store.guild_set(g, drop_channel=556)
        now = dt.datetime(2026, 10, 15, 19, 0, tzinfo=config.TZ)
        dms = []

        async def send(**kwargs):
            dms.append(kwargs)

        async def go():
            broken = FakeChannel(fail=True)
            with mock.patch.object(self.bot, "get_channel", lambda cid: broken), \
                    mock.patch.object(self.bot, "get_guild", lambda gid: FakeGuild(gone={13})), \
                    mock.patch.object(self.bot, "get_user", lambda uid: SimpleNamespace(send=send)), \
                    mock.patch.object(sys.modules[type(cog).__module__], "banner_file",
                                      side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    await cog.maybe_remind(g, now)
            self.assertIsNone(self.store.meta_get(f"remind_sent:{g}"))  # not marked: retried later
            self.assertNotIn(13, R.subscribers(self.store, g))  # left the server: unsubscribed
            ok = FakeChannel()
            with mock.patch.object(self.bot, "get_channel", lambda cid: ok), \
                    mock.patch.object(self.bot, "get_guild", lambda gid: FakeGuild()):
                self.assertEqual(await cog.maybe_remind(g, now), 2)
            self.assertEqual(len(ok.sent), 2)  # one message per kind of reminder
            titles = sorted(str(m["view"].to_components()) for m in ok.sent)
            self.assertTrue(any("La case du 15 octobre" in t and "Coffre du jour" not in t for t in titles))
            self.assertTrue(any("Ton coffre du jour" in t for t in titles))
            self.store.meta_del(f"remind_sent:{g}")
            with mock.patch.object(self.bot, "get_channel", lambda cid: FakeChannel(fail=True)), \
                    mock.patch.object(self.bot, "get_guild", lambda gid: FakeGuild()), \
                    mock.patch.object(self.bot, "get_user", lambda uid: SimpleNamespace(send=send)):
                self.assertEqual(await cog.maybe_remind(g, now), 2)  # channel refused: private messages
            self.assertEqual(len(dms), 2)
        asyncio.run(go())

    def test_calendar_button(self):
        from halloween.cogs import seasonal

        async def go():
            u = 9901
            with mock.patch.object(seasonal, "october_day", lambda now=None: (2026, 12)):
                v = seasonal.CalendarView(self.bot, FakeInteraction(user=FakeUser(u), client=self.bot))
                v.render()
                check_layout(v)
                await v._remind(FakeInteraction(user=FakeUser(u), client=self.bot))
                self.assertTrue(R.is_subscribed(self.store, v.guild_id, u))
                self.assertIn("Rappel activé", v.result)
                check_layout(v)
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
