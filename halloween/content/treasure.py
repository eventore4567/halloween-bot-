"""La Chasse au trésor du serveur: four enigmas generated from a seed.

1. ``cipher``  a word shifted along the alphabet (Caesar), the shift shown on a cipher wheel.
2. ``scroll``  an anagram written on a parchment hidden in another channel of the server.
3. ``status``  a word written backwards in the bot's own status.
4. ``grid``    a word search: the final word is the only word of the grid that starts with the
               last letter of answer 3 and has the given length.
"""
from __future__ import annotations

import random
import string
import unicodedata
from dataclasses import dataclass

WORDS = ["LANTERNE", "CHAUDRON", "SORCIERE", "VAMPIRE", "SQUELETTE", "ARAIGNEE", "CIMETIERE", "FANTOME",
         "CITROUILLE", "GRIMOIRE", "MOMIE", "CERCUEIL", "CHOUETTE", "CORBEAU", "BOUGIE", "POTION", "BALAI",
         "CHAUVESOURIS", "LOUPGAROU", "CRYPTE", "MANOIR", "BRUME", "TOMBEAU", "SPECTRE", "DEMON", "HIBOU",
         "MALEFICE", "SORTILEGE", "ENVOUTEMENT", "MASQUE", "BONBON", "EPOUVANTAIL", "OSSEMENT", "GOBELIN",
         "PLEINELUNE", "MINUIT", "TOILE", "GRIFFE", "CROC", "ELIXIR", "AMULETTE", "RELIQUE"]
GRID = 10
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)]  # right, down, diagonal, and two backwards


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.upper())
    return "".join(c for c in text if c in string.ascii_uppercase)


def shift(word: str, k: int) -> str:
    return "".join(chr((ord(c) - 65 + k) % 26 + 65) for c in word)


@dataclass
class Hunt:
    seed: int
    answers: list[str]
    cipher_shift: int
    cipher_text: str
    anagram: str
    reversed_word: str
    grid: list[str]
    final_len: int
    final_first: str


def _place(grid, word, rnd) -> bool:
    for _ in range(400):
        dx, dy = rnd.choice(DIRECTIONS)
        x0, y0 = rnd.randrange(GRID), rnd.randrange(GRID)
        cells = [(x0 + dx * i, y0 + dy * i) for i in range(len(word))]
        if all(0 <= x < GRID and 0 <= y < GRID and grid[y][x] in (".", word[i]) for i, (x, y) in enumerate(cells)):
            for i, (x, y) in enumerate(cells):
                grid[y][x] = word[i]
            return True
    return False


def _anagram(word: str, rnd) -> str:
    letters = list(word)
    for _ in range(20):
        rnd.shuffle(letters)
        if "".join(letters) != word:
            break
    return "".join(letters)


def make_hunt(seed: int) -> Hunt:
    rnd = random.Random(seed)
    pool = [w for w in WORDS if 5 <= len(w) <= 10]
    w1, w2 = rnd.sample(pool, 2)

    def finals(w3):
        return [w for w in WORDS if w[0] == w3[-1] and 5 <= len(w) <= GRID and w not in (w1, w2, w3)]

    # answer 3 is drawn among the words that leave a final word starting with its last letter
    w3 = rnd.choice([w for w in pool if w not in (w1, w2) and finals(w)])
    w4 = rnd.choice(finals(w3))
    first = w3[-1]
    while True:
        grid = [["."] * GRID for _ in range(GRID)]
        if not _place(grid, w4, rnd):
            continue
        # decoys: other words, never both starting with ``first`` and having the final length
        decoys = [w for w in WORDS if len(w) <= GRID and w != w4 and not (w[0] == first and len(w) == len(w4))]
        for d in rnd.sample(decoys, 4):
            _place(grid, d, rnd)
        for row in grid:
            for x, c in enumerate(row):
                if c == ".":
                    row[x] = rnd.choice(string.ascii_uppercase)
        lines = ["".join(r) for r in grid]
        rivals = [w for w in WORDS if w != w4 and w[0] == first and len(w) == len(w4)]
        if _count(lines, w4) == 1 and not any(_count(lines, w) for w in rivals):
            break
    k = rnd.randint(3, 23)
    return Hunt(seed, [w1, w2, w3, w4], k, shift(w1, k), _anagram(w2, rnd), w3[::-1], lines, len(w4), first)


def _count(lines: list[str], word: str) -> int:
    """How many times ``word`` can be read in the grid, in the hunt's directions."""
    n = 0
    for y in range(GRID):
        for x in range(GRID):
            for dx, dy in DIRECTIONS:
                cells = [(x + dx * i, y + dy * i) for i in range(len(word))]
                if all(0 <= cx < GRID and 0 <= cy < GRID for cx, cy in cells) and \
                        "".join(lines[cy][cx] for cx, cy in cells) == word:
                    n += 1
    return n


def check(hunt: Hunt, step: int, answer: str) -> bool:
    return normalize(answer) == hunt.answers[step]


STEPS = [
    dict(title="Le message chiffré", icon="lock"),
    dict(title="Le parchemin caché", icon="scroll"),
    dict(title="La voix du bot", icon="crystal"),
    dict(title="La grille maudite", icon="eye"),
]
