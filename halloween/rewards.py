"""Shared reward logic: candies + XP + level-up bonus, with a ready-made line."""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from .emojis import E


@dataclass
class Reward:
    candies: int = 0
    xp: int = 0
    old_level: int = 1
    new_level: int = 1
    level_bonus: int = 0

    @property
    def leveled(self) -> bool:
        return self.new_level > self.old_level

    def line(self) -> str:
        parts = []
        if self.candies:
            parts.append(f"**+{config.fmt(self.candies)}** {E.candy}")
        if self.xp:
            parts.append(f"**+{self.xp}** XP {E.star}")
        text = " · ".join(parts)
        if self.leveled:
            text += (f"\n{E.sparkle} **NIVEAU {self.new_level} !** Tu deviens "
                     f"**{config.rank_title(self.new_level)}** · bonus **+{config.fmt(self.level_bonus)}** {E.candy}")
        return text


def grant(store, guild_id: int, user_id: int, candies: int = 0, xp: int = 0, reason: str = "jeu") -> Reward:
    r = Reward()
    if candies:
        r.candies = store.add_candies(guild_id, user_id, candies, reason)
    if xp:
        before = store.player(guild_id, user_id)["xp"]
        r.old_level, r.new_level = store.add_xp(guild_id, user_id, xp)
        r.xp = store.player(guild_id, user_id)["xp"] - before
        if r.leveled:
            bonus = sum(50 * lvl for lvl in range(r.old_level + 1, r.new_level + 1))
            r.level_bonus = store.add_candies(guild_id, user_id, bonus, "niveau", boost=False)
    return r
