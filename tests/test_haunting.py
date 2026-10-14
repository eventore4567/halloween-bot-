"""La Hantise: the server drawn as a haunted castle, and the Spectre chased by talking in a channel."""
import asyncio
import itertools
import sys
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot
from PIL import Image

from halloween.art import castle as art


class Perms(SimpleNamespace):
    pass


class FakeCategory:
    def __init__(self, name, position):
        self.name, self.position = name, position


class FakeChannel:
    def __init__(self, cid, name, category=None, position=0, public=True):
        self.id, self.name, self.category, self.position, self.public = cid, name, category, position, public
        self.nsfw = False
        self.sent = []
        self.mention = f"<#{cid}>"

    def permissions_for(self, who):
        ok = self.public or who == "me"
        return Perms(view_channel=ok, send_messages=ok, attach_files=True)

    async def send(self, content=None, **kwargs):
        self.sent.append(dict(kwargs, content=content))


class FakeGuild:
    def __init__(self, gid, channels):
        self.id = gid
        self.name = "Serveur 🎃 test"
        self.text_channels = channels
        self.me = "me"
        self.default_role = "everyone"


class FakeMessage:
    def __init__(self, guild, author, channel):
        self.guild, self.author, self.channel = guild, author, channel


class ArtTest(unittest.TestCase):
    def test_map_and_clips(self):
        floors = [art.Floor(f"Étage {f} 🎮", [art.Room(f * 10 + i, f"salon-{i}-🔥", i / 5, i % 2 == 0,
                                                       [(900 + i, None)] * (i % 3)) for i in range(6)], more=2)
                  for f in range(6)]
        png = Image.open(BytesIO(art.map_png("Un serveur", floors, 13)))
        self.assertEqual(png.size, (art.W, art.height(6)))
        for data in (art.haunt_gif("S", floors, 13, "LE SPECTRE HANTE #X !"),
                     art.exorcism_gif("S", floors, 13, "#X EST LIBÉRÉ !")):
            self.assertGreater(Image.open(BytesIO(data)).n_frames, 10)
        self.assertEqual(art.clean("🎃-général-💬"), "général")
        self.assertEqual(art.clean("🎃"), "salon")


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.cog = cls.bot.get_cog("Haunting")
        cls.mod = sys.modules[type(cls.cog).__module__]

    def setUp(self):
        hall = FakeCategory("Accueil", 0)
        chat = FakeCategory("Discussion", 1)
        self.events = FakeChannel(1, "evenements", hall, 0)
        self.general = FakeChannel(2, "general", chat, 0)
        self.dead = FakeChannel(3, "salon-oublie", chat, 1)
        self.staff = FakeChannel(4, "staff", chat, 2, public=False)
        self.guild = FakeGuild(81, [self.events, self.general, self.dead, self.staff])
        self.users = [FakeUser(8100 + k, f"Membre{k}") for k in range(4)]
        self.store.guild_set(81, drop_channel=1, drops_on=1)
        self.cog.cache.pop(81, None)
        self.cog.where.pop(81, None)
        self.cog.activity.pop(81, None)
        self.store.meta_del("haunt:81")
        self.clock = itertools.count(10**9, 5)  # every message 5 s after the previous one

    def say(self, user, channel):
        return self.cog.on_message(FakeMessage(self.guild, user, channel))

    def run_flow(self, coro):
        with mock.patch.object(self.mod.time, "time", lambda: next(self.clock)), \
                mock.patch.object(self.bot, "get_channel", lambda cid: {1: self.events, 2: self.general,
                                                                        3: self.dead}.get(cid)):
            return asyncio.run(coro)

    def test_haunt_and_exorcism(self):
        async def go():
            self.assertEqual(await self.cog.step(self.guild), "waiting")  # nobody talks yet
            for _ in range(5):
                for u in self.users[:3]:
                    await self.say(u, self.general)
            self.assertEqual(await self.cog.step(self.guild), "haunted")
            st = self.cog.state(81)
            self.assertEqual(st["room"], self.dead.id)  # the quietest public channel, never the private one
            self.assertEqual(len(self.dead.sent), 1)
            check_layout(self.dead.sent[0]["view"])
            self.assertIn("Le Spectre hante <#3>", self.events.sent[-1]["content"])  # the events channel is told
            for _ in range(10):  # one member alone cannot chase it
                await self.say(self.users[0], self.dead)
            self.assertEqual(self.cog.state(81)["room"], self.dead.id)
            for u in self.users[1:3]:
                for _ in range(4):
                    await self.say(u, self.dead)
            st = self.cog.state(81)
            self.assertIsNone(st["room"])
            self.assertIn(self.dead.id, st["lit"])
            self.assertEqual(st["exorcisms"], 1)
            for u in self.users[:3]:
                self.assertEqual(self.store.stats(81, u.id).get("exorcisms"), 1)
            self.assertNotIn("exorcisms", self.store.stats(81, self.users[3].id))
            check_layout(self.dead.sent[-1]["view"])
        self.run_flow(go())

    def test_escape_and_rest(self):
        async def go():
            await self.cog.haunt(self.guild, self.general)
            self.assertEqual(await self.cog.step(self.guild), "haunting")
            st = self.cog.state(81)
            st["deadline"] = 0
            self.assertEqual(await self.cog.step(self.guild), "escaped")
            self.assertIsNone(self.cog.state(81)["room"])
            self.assertEqual(await self.cog.step(self.guild), "waiting")  # it rests before coming back
        self.run_flow(go())

    def test_castle_map_command(self):
        async def go():
            for u, ch in zip(self.users, (self.general, self.general, self.dead, self.events)):
                await self.say(u, ch)
            floors = await self.cog.floors(self.guild)
            names = [[r.name for r in f.rooms] for f in floors]
            self.assertEqual(names, [["evenements"], ["general", "salon-oublie"]])  # staff is private
            general = floors[1].rooms[0]
            self.assertEqual((general.activity, len(general.people)), (1.0, 2))
            inter = FakeInteraction(user=self.users[0], client=self.bot, guild_id=81)
            inter.guild = self.guild
            await self.cog.open(inter)
            kind, kwargs = inter.response.sent[-1]
            self.assertEqual(kind, "followup")
            check_layout(kwargs["view"])
        self.run_flow(go())


if __name__ == "__main__":
    unittest.main()
