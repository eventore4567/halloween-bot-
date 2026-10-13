"""Le Traître: the rules of the social deduction game, with no Discord in them.

Vampires hide among the villagers of Brumeval. Every night the vampires pick a
victim, the Medium learns one player's role and the Guardian protects someone.
Every day the village debates and votes to banish one suspect. The village wins
when every vampire is gone; the vampires win as soon as they are as many as the
others.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

MIN_PLAYERS, MAX_PLAYERS = 4, 12

ROLES = {
    "vampire": dict(name="Vampire", team="vampires", emoji="vampire", color="red",
                    desc="Chaque nuit, choisis avec les autres vampires qui sera mordu. Le jour, fais-toi passer "
                         "pour un villageois… et accuse les autres."),
    "medium": dict(name="Médium", team="village", emoji="crystal", color="purple",
                   desc="Chaque nuit, ta boule de cristal te révèle le vrai rôle d'un joueur. "
                        "Guide le village sans te faire repérer par les vampires !"),
    "guardian": dict(name="Gardien", team="village", emoji="shield", color="blue",
                     desc="Chaque nuit, protège un joueur (toi compris) : s'il est attaqué, il survit. "
                          "Jamais deux nuits de suite la même personne."),
    "villager": dict(name="Villageois", team="village", emoji="pumpkin", color="orange",
                     desc="Pas de pouvoir, mais ta voix compte : écoute, observe les hésitations "
                          "et vote pour démasquer les vampires."),
}
NIGHT_ROLES = ("vampire", "medium", "guardian")
SKIP = 0  # vote for nobody


def vampire_count(n: int) -> int:
    return 1 if n <= 6 else 2 if n <= 10 else 3


def deal(n: int, rnd=random) -> list[str]:
    """Roles for ``n`` players, shuffled."""
    roles = ["vampire"] * vampire_count(n) + ["medium"]
    if n >= 5:
        roles.append("guardian")
    roles += ["villager"] * (n - len(roles))
    rnd.shuffle(roles)
    return roles


@dataclass
class Game:
    players: list[int]
    roles: dict[int, str] = field(default_factory=dict)
    alive: list[int] = field(default_factory=list)
    night: int = 0
    bites: dict[int, int] = field(default_factory=dict)  # vampire -> target
    seen: dict[int, dict[int, str]] = field(default_factory=dict)  # medium -> {target: role}
    looked: set[int] = field(default_factory=set)  # mediums who already looked tonight
    guard: int | None = None
    last_guard: int | None = None
    votes: dict[int, int] = field(default_factory=dict)  # voter -> target (SKIP = nobody)
    ready: set[int] = field(default_factory=set)

    @classmethod
    def start(cls, players: list[int], rnd=random) -> "Game":
        g = cls(list(players))
        g.roles = dict(zip(g.players, deal(len(g.players), rnd)))
        g.alive = list(g.players)
        return g

    # ----------------------------------------------------------------- views
    def role(self, uid: int) -> str:
        return self.roles[uid]

    def is_alive(self, uid: int) -> bool:
        return uid in self.alive

    def team(self, uid: int) -> str:
        return ROLES[self.roles[uid]]["team"]

    def vampires(self, alive_only=True) -> list[int]:
        pool = self.alive if alive_only else self.players
        return [u for u in pool if self.roles[u] == "vampire"]

    def winner(self) -> str | None:
        vamps = len(self.vampires())
        if vamps == 0:
            return "village"
        if vamps >= len(self.alive) - vamps:
            return "vampires"
        return None

    # ----------------------------------------------------------------- night
    def begin_night(self):
        self.night += 1
        self.bites.clear()
        self.looked.clear()
        self.guard = None

    def targets(self, uid: int) -> list[int]:
        """Who ``uid`` may pick tonight."""
        role = self.roles[uid]
        if role == "vampire":
            return [u for u in self.alive if self.roles[u] != "vampire"]
        if role == "medium":
            return [u for u in self.alive if u != uid]
        if role == "guardian":
            return [u for u in self.alive if u != self.last_guard]
        return []

    def act(self, uid: int, target: int) -> str | None:
        """Record a night action. Returns the role seen by a medium, else None. Raises ValueError if not allowed."""
        if not self.is_alive(uid) or target not in self.targets(uid):
            raise ValueError("action not allowed")
        role = self.roles[uid]
        if role == "vampire":
            self.bites[uid] = target
        elif role == "medium":
            if uid in self.looked:
                raise ValueError("already looked tonight")
            self.looked.add(uid)
            self.seen.setdefault(uid, {})[target] = self.roles[target]
            return self.roles[target]
        elif role == "guardian":
            self.guard = target
        return None

    def pending_night(self) -> list[int]:
        """Night players who have not acted yet."""
        out = []
        for u in self.alive:
            role = self.roles[u]
            if (role == "vampire" and u not in self.bites) or (role == "medium" and u not in self.looked) \
                    or (role == "guardian" and self.guard is None):
                out.append(u)
        return out

    def resolve_night(self, rnd=random) -> tuple[int | None, bool]:
        """(victim, saved): the most chosen target dies unless the guardian protected them."""
        if self.guard is not None:
            self.last_guard = self.guard
        else:
            self.last_guard = None
        if not self.bites:  # the vampires fell asleep: one of them still bites someone at random
            options = [u for u in self.alive if self.roles[u] != "vampire"]
            target = rnd.choice(options) if options else None
        else:
            counts = Counter(self.bites.values())
            top = max(counts.values())
            target = rnd.choice(sorted(t for t, c in counts.items() if c == top))
        if target is None:
            return None, False
        if target == self.guard:
            return target, True
        self.alive.remove(target)
        return target, False

    # ------------------------------------------------------------------- day
    def mark_ready(self, uid: int) -> bool:
        """True once a majority of the living is ready to vote."""
        if self.is_alive(uid):
            self.ready.add(uid)
        return len(self.ready) * 2 > len(self.alive)

    def begin_vote(self):
        self.votes.clear()
        self.ready.clear()

    def vote(self, voter: int, target: int):
        if not self.is_alive(voter) or (target != SKIP and not self.is_alive(target)):
            raise ValueError("vote not allowed")
        self.votes[voter] = target

    def all_voted(self) -> bool:
        return all(u in self.votes for u in self.alive)

    def tally(self) -> Counter:
        return Counter(t for t in self.votes.values() if t != SKIP)

    def resolve_vote(self) -> int | None:
        """The player with strictly the most votes is banished; a tie (or more skips) saves everyone."""
        counts = self.tally()
        skips = sum(1 for t in self.votes.values() if t == SKIP)
        if not counts:
            return None
        ranked = counts.most_common()
        top, n = ranked[0]
        if (len(ranked) > 1 and ranked[1][1] == n) or skips >= n:
            return None
        self.alive.remove(top)
        return top
