"""Test doubles: a bot with every cog loaded (no login) and fake interactions."""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_PATH", ":memory:")

import discord  # noqa: E402

from main import COGS, NuitHantee  # noqa: E402


class FakeAvatar:
    def replace(self, **kwargs):
        return self

    async def read(self):
        return None


class FakeUser(SimpleNamespace):
    def __init__(self, uid=111, name="Tomioka"):
        super().__init__(id=uid, display_name=name, name=name, bot=False, mention=f"<@{uid}>",
                         display_avatar=FakeAvatar())


class FakeResponse:
    def __init__(self):
        self.sent = []
        self._done = False

    def is_done(self):
        return self._done

    async def send_message(self, *args, **kwargs):
        self._done = True
        self.sent.append(("send", kwargs))

    async def edit_message(self, *args, **kwargs):
        self._done = True
        self.sent.append(("edit", kwargs))

    async def defer(self, *args, **kwargs):
        self._done = True
        self.sent.append(("defer", kwargs))

    async def send_modal(self, modal):
        self._done = True
        self.sent.append(("modal", modal))


class FakeFollowup:
    def __init__(self, response):
        self.response = response

    async def send(self, *args, **kwargs):
        self.response.sent.append(("followup", kwargs))
        return None


class FakeInteraction:
    def __init__(self, user=None, guild_id=999, data=None, client=None, message=None):
        self.user = user or FakeUser()
        self.guild_id = guild_id
        self.guild = None
        self.message = message
        self.data = data or {}
        self.response = FakeResponse()
        self.followup = FakeFollowup(self.response)
        self.client = client
        self.channel = None

    async def original_response(self):
        return None

    async def edit_original_response(self, **kwargs):
        self.response.sent.append(("edit_original", kwargs))
        return None


def make_bot():
    bot = NuitHantee()

    async def fetch_user(uid):  # no gateway/HTTP in tests
        return FakeUser(uid, f"Joueur {uid}")
    bot.fetch_user = fetch_user

    async def load():
        for name in COGS:
            await bot.load_extension(f"halloween.cogs.{name}")
    asyncio.run(load())
    return bot


def walk(components):
    for comp in components:
        yield comp
        for key in ("components",):
            if key in comp:
                yield from walk(comp[key])
        if "accessory" in comp:
            yield comp["accessory"]


def check_layout(view: discord.ui.LayoutView):
    """Raise AssertionError if the payload breaks a Discord Components V2 limit."""
    payload = view.to_components()
    comps = list(walk(payload))
    assert len(comps) <= 40, f"{len(comps)} components (max 40)"
    text = sum(len(c.get("content", "")) for c in comps if c.get("type") == 10)
    assert text <= 4000, f"{text} characters of text (max 4000)"
    for c in comps:
        if c.get("type") == 1:
            assert 1 <= len(c["components"]) <= 5, "action row must hold 1 to 5 items"
        if c.get("type") == 2 and c.get("label"):
            assert len(c["label"]) <= 80, c["label"]
        if c.get("type") == 3:
            assert 1 <= len(c["options"]) <= 25
            for o in c["options"]:
                assert len(o["label"]) <= 100 and len(o.get("description") or "") <= 100
    return comps


class FakeEmoji:
    """Stands in for an uploaded application emoji (worst-case text length)."""

    def __init__(self, name, animated, idx):
        self.name = "nh_" + name
        self.id = 1_400_000_000_000_000_000 + idx
        self.animated = animated

    def __str__(self):
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


def install_fake_emojis():
    from halloween.art.emoji_art import EMOJIS
    from halloween.emojis import E
    for i, (key, spec) in enumerate(EMOJIS.items()):
        E.custom[key] = FakeEmoji(key, spec.frames > 1, i)
