"""Maze logic for the haunted labyrinth: generation with a few loops, path finding, the ghost's moves."""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

N = 9  # cells per side
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _edge(a, b):
    return (a, b) if a < b else (b, a)


@dataclass
class Maze:
    passages: set = field(default_factory=set)
    start: tuple = (0, 0)
    exit: tuple = (N - 1, N - 1)
    key: tuple = (0, 0)
    candle: tuple = (0, 0)
    candies: set = field(default_factory=set)
    ghost: tuple = (0, 0)

    def open(self, a, b) -> bool:
        return _edge(a, b) in self.passages

    def neighbours(self, cell):
        x, y = cell
        for dx, dy in DIRS.values():
            nxt = (x + dx, y + dy)
            if 0 <= nxt[0] < N and 0 <= nxt[1] < N and self.open(cell, nxt):
                yield nxt

    def distances(self, origin) -> dict:
        dist = {origin: 0}
        todo = deque([origin])
        while todo:
            cur = todo.popleft()
            for nxt in self.neighbours(cur):
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1
                    todo.append(nxt)
        return dist

    def step_towards(self, origin, target):
        """Next cell on a shortest path from ``origin`` to ``target``."""
        dist = self.distances(target)
        return min(self.neighbours(origin), key=lambda c: (dist.get(c, 999), c), default=origin)


def generate(seed: int, loops: int = 14, candies: int = 5) -> Maze:
    rnd = random.Random(seed)
    m = Maze()
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:  # recursive backtracker: a perfect maze
        x, y = stack[-1]
        options = [(x + dx, y + dy) for dx, dy in DIRS.values()
                   if 0 <= x + dx < N and 0 <= y + dy < N and (x + dx, y + dy) not in seen]
        if not options:
            stack.pop()
            continue
        nxt = rnd.choice(options)
        m.passages.add(_edge((x, y), nxt))
        seen.add(nxt)
        stack.append(nxt)
    walls = [_edge((x, y), (x + dx, y + dy)) for x in range(N) for y in range(N) for dx, dy in ((1, 0), (0, 1))
             if x + dx < N and y + dy < N]
    walls = [w for w in walls if w not in m.passages]
    for w in rnd.sample(walls, min(loops, len(walls))):  # loops, so the ghost can be dodged
        m.passages.add(w)
    from_start = m.distances(m.start)
    ends = [c for c in from_start if c not in (m.start, m.exit)]
    corners = [(0, N - 1), (N - 1, 0)]
    m.key = max(ends, key=lambda c: (min(abs(c[0] - k[0]) + abs(c[1] - k[1]) for k in corners) == 0,
                                     from_start[c] + rnd.random()))
    free = [c for c in ends if c != m.key]
    m.ghost = max(free, key=lambda c: (from_start[c] - abs(c[0] - m.exit[0]) - abs(c[1] - m.exit[1]),
                                       rnd.random()))
    free = [c for c in free if c != m.ghost and from_start[c] > 2]
    m.candle = rnd.choice(free)
    free.remove(m.candle)
    m.candies = set(rnd.sample(free, min(candies, len(free))))
    return m
