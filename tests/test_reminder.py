"""Opt-in daily reminder for the October calendar and the daily chest."""
import asyncio
import datetime as dt
import unittest
from types import SimpleNamespace
from unittest import mock

import discord
from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween import config
from halloween.cogs import reminder as R


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)


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
        for day, server in ((14, None), (31, None), (None, None), (14, "Mon serveur")):
            view = R.reminder_view(day, [1, 2, 3], server)
            check_layout(view)

    def test_sends_once_a_day_after_the_hour(self):
        g = 4343
        cog = self.bot.get_cog("Reminder")
        R.toggle(self.store, g, 77)
        channel = FakeChannel()
        self.store.guild_set(g, drop_channel=555)

        async def go():
            with mock.patch.object(self.bot, "get_channel", lambda cid: channel if cid == 555 else None):
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
                    mock.patch.object(self.bot, "get_guild", lambda gid: SimpleNamespace(name="Serveur test")):
                now = dt.datetime(2026, 10, 20, 21, 0, tzinfo=config.TZ)
                self.assertEqual(await cog.maybe_remind(g, now), 1)
            self.assertEqual(len(got), 1)
            self.assertIsInstance(got[0]["view"], discord.ui.LayoutView)
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
