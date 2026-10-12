"""Application emoji registry.

On start-up the bot uploads its own drawn emojis to the Discord application
(Developer Portal > Emojis). They are usable in every server, in messages,
buttons and select menus. Until the upload is done (or if it fails) every
icon gracefully falls back to a standard Unicode emoji.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

import discord

from .art.emoji_art import EMOJIS, PREFIX, render_emoji

LOG = logging.getLogger(__name__)


class EmojiPack:
    def __init__(self):
        self.custom: dict[str, discord.Emoji] = {}

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.get(name)

    def get(self, name: str) -> str:
        em = self.custom.get(name)
        if em:
            return str(em)
        spec = EMOJIS.get(name)
        return spec.fallback if spec else "▫️"

    def __call__(self, name: str) -> str:
        return self.get(name)

    def partial(self, name: str):
        """For buttons / select options."""
        em = self.custom.get(name)
        if em:
            return discord.PartialEmoji(name=em.name, id=em.id, animated=em.animated)
        spec = EMOJIS.get(name)
        return spec.fallback if spec else None

    def url(self, name: str) -> str | None:
        em = self.custom.get(name)
        if not em:
            return None
        ext = "gif" if em.animated else "png"
        return f"https://cdn.discordapp.com/emojis/{em.id}.{ext}?size=128&quality=lossless"

    def bar(self, value: float, total: float, length: int = 8) -> str:
        """Progress bar made of custom emoji pieces."""
        ratio = 0 if total <= 0 else max(0.0, min(1.0, value / total))
        filled = round(ratio * length)
        if not self.custom.get("bar_m1"):
            return "▰" * filled + "▱" * (length - filled)
        out = []
        for i in range(length):
            on = "1" if i < filled else "0"
            part = "l" if i == 0 else ("r" if i == length - 1 else "m")
            out.append(self.get(f"bar_{part}{on}"))
        return "".join(out)


E = EmojiPack()


def _digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:12]


async def sync_emojis(bot, store) -> dict:
    """Create / refresh the bot's application emojis. Safe to run at every boot."""
    report = {"created": 0, "updated": 0, "kept": 0, "failed": 0}
    try:
        existing = await bot.fetch_application_emojis()
    except (discord.HTTPException, AttributeError) as exc:
        LOG.warning("Cannot list application emojis (%s); using Unicode fallbacks.", exc)
        return report
    by_name = {em.name: em for em in existing}
    hashes = store.meta_get("emoji_hashes", {})
    loop = asyncio.get_running_loop()
    for key in EMOJIS:
        name = PREFIX + key
        try:
            data = await loop.run_in_executor(None, render_emoji, key)
        except Exception:  # pragma: no cover - art bug must not stop the bot
            LOG.exception("Rendering emoji %s failed", key)
            report["failed"] += 1
            continue
        digest = _digest(data)
        current = by_name.get(name)
        if current and hashes.get(name) == digest:
            E.custom[key] = current
            report["kept"] += 1
            continue
        try:
            if current:
                await current.delete()
            created = await bot.create_application_emoji(name=name, image=data)
        except discord.HTTPException as exc:
            LOG.warning("Emoji %s upload failed: %s", name, exc)
            if current:
                E.custom[key] = current
            report["failed"] += 1
            continue
        E.custom[key] = created
        hashes[name] = digest
        store.meta_set("emoji_hashes", hashes)
        report["updated" if current else "created"] += 1
        await asyncio.sleep(0.3)
    LOG.info("Emoji pack ready: %s", report)
    return report
