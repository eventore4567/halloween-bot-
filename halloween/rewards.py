"""Shared reward logic: candies + XP + level-up bonus + achievements, with a ready-made line."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .emojis import E


@dataclass
class Reward:
    candies: int = 0
    xp: int = 0
    old_level: int = 1
    new_level: int = 1
    level_bonus: int = 0
    achievements: list = field(default_factory=list)

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
        for ach in self.achievements:
            text += f"\n{E.trophy} **Succès débloqué : {ach[1]}** {E(ach[3])} · **+{config.fmt(ach[6])}** {E.candy}"
        return text.strip()


def measures(store, guild_id: int, user_id: int) -> dict:
    values = dict(store.stats(guild_id, user_id))
    p = store.player(guild_id, user_id)
    values["level"] = config.level_from_xp(p["xp"])[0]
    values["earned"] = p["earned"]
    values["streak"] = p["streak"]
    values["cards"] = len(store.cards(guild_id, user_id))
    return values


def check_achievements(store, guild_id: int, user_id: int) -> list:
    """Unlock every achievement whose goal is reached; pay their bonus once."""
    owned = store.owned(guild_id, user_id)
    pending = [a for a in config.ACHIEVEMENTS if "ach:" + a[0] not in owned]
    if not pending:
        return []
    values = measures(store, guild_id, user_id)
    new = []
    for ach in pending:
        if values.get(ach[4], 0) >= ach[5] and store.unlock(guild_id, user_id, "ach:" + ach[0]):
            store.add_candies(guild_id, user_id, ach[6], "succes", boost=False)
            new.append(ach)
    return new


def grant(store, guild_id: int, user_id: int, candies: int = 0, xp: int = 0, reason: str = "jeu",
          stats: dict | None = None, best: dict | None = None) -> Reward:
    """Pay a reward. ``stats`` are added, ``best`` keep their maximum, before achievements are checked."""
    r = Reward()
    for key, amount in (stats or {}).items():
        store.stat_add(guild_id, user_id, key, amount)
    for key, value in (best or {}).items():
        store.stat_max(guild_id, user_id, key, value)
    if candies:
        r.candies = store.add_candies(guild_id, user_id, candies, reason)
    if xp:
        before = store.player(guild_id, user_id)["xp"]
        r.old_level, r.new_level = store.add_xp(guild_id, user_id, xp)
        r.xp = store.player(guild_id, user_id)["xp"] - before
        if r.leveled:
            bonus = sum(50 * lvl for lvl in range(r.old_level + 1, r.new_level + 1))
            r.level_bonus = store.add_candies(guild_id, user_id, bonus, "niveau", boost=False)
    r.achievements = check_achievements(store, guild_id, user_id)
    return r
