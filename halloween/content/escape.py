"""Procedural puzzles for the cooperative escape game.

Every room has a code and 4 clue fragments; fragments are dealt to the players,
so nobody can open a door alone: they have to talk.
"""
from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

FACTS = [
    ("le nombre de pattes d'une araignée", 8), ("le nombre de jours dans une semaine", 7),
    ("le nombre de côtés d'un triangle", 3), ("le nombre de doigts d'une main", 5),
    ("le nombre de saisons dans une année", 4), ("le nombre de pattes d'un chat noir", 4),
    ("le nombre de lettres dans « LUNE »", 4), ("le nombre de lettres dans « CRÂNE »", 5),
    ("le nombre de lettres dans « FANTÔME »", 7), ("le nombre de lettres dans « SORCIÈRE »", 8),
    ("le nombre de cornes d'un diable", 2), ("le nombre d'yeux d'un cyclope", 1),
    ("le nombre de zéros dans 1 000", 3), ("le nombre d'heures entre minuit et 9 h", 9),
    ("le nombre de roues d'un tricycle", 3), ("le nombre de pattes d'une chauve-souris", 2),
    ("le nombre de lettres dans « BOUH »", 4), ("le nombre de lettres dans « VAMPIRE »", 7),
]
WORDS5 = ["TOMBE", "BALAI", "MOMIE", "HIBOU", "OMBRE", "BRUME", "DEMON", "ORAGE", "CAPES", "SORTS"]
VOCAB = ["CITROUILLE", "FANTOME", "SORCIERE", "VAMPIRE", "SQUELETTE", "CHAUDRON", "ARAIGNEE", "CIMETIERE",
         "CORBEAU", "GRIMOIRE", "LANTERNE", "MALEFICE", "POTION", "BALAI", "HIBOU", "BONBON", "CRYPTE", "DEMON",
         "MOMIE", "TOMBE", "BRUME", "ORAGE", "SPECTRE", "MINUIT", "LOUP", "CAPE", "SORT"]
ORDINALS = ["1re", "2e", "3e", "4e", "5e", "6e", "7e", "8e", "9e", "10e"]


@dataclass
class Room:
    title: str
    intro: str
    code: str
    clues: list[str]
    kind: str  # "digits", "word" or "sum"


def _digit_clue(rnd, pos: int, digit: int) -> str:
    options = []
    for text, value in FACTS:
        delta = digit - value
        if delta == 0:
            options.append(f"Le chiffre n°{pos} est {text}.")
        elif 0 < delta <= 4:
            options.append(f"Le chiffre n°{pos} vaut {text}, plus {delta}.")
        elif -4 <= delta < 0:
            options.append(f"Le chiffre n°{pos} vaut {text}, moins {-delta}.")
    return rnd.choice(options)


def candle_room(rnd) -> Room:
    digits = [rnd.randint(1, 9) for _ in range(4)]
    clues = [_digit_clue(rnd, i + 1, d) for i, d in enumerate(digits)]
    return Room("La Crypte des chandelles",
                "Un cadenas à **4 chiffres** scelle la grille. Des chandelles éclairent des inscriptions…",
                "".join(map(str, digits)), clues, "digits")


def _letter_clue(rnd, pos: int, letter: str) -> str:
    words = [w for w in VOCAB if letter in w]
    word = rnd.choice(words)
    idx = word.index(letter)
    return f"La lettre n°{pos} est la {ORDINALS[idx]} lettre de « {word} »."


def library_room(rnd) -> Room:
    word = rnd.choice(WORDS5)
    clues = [_letter_clue(rnd, i + 1, ch) for i, ch in enumerate(word)]
    # 5 letters, 4 fragments: the last fragment carries two letters
    merged = clues[:3] + [clues[3] + " " + clues[4]]
    return Room("La Bibliothèque maudite",
                "Un grimoire verrouillé attend un **mot de 5 lettres**. Les pages murmurent des indices…",
                word, merged, "word")


def vault_room(rnd) -> Room:
    numbers = [rnd.randint(11, 49) for _ in range(3)]
    minus = rnd.choice([5, 10, 15, 20])
    total = sum(numbers) - minus
    clues = [f"Sur ton parchemin est gravé le nombre **{n}**." for n in numbers]
    clues.append(f"Ton parchemin dit : « Retranchez **{minus}** à la somme des autres nombres gravés. »")
    rnd.shuffle(clues)
    return Room("La Porte du Caveau",
                "La dernière porte s'ouvre avec **un seul nombre** : il faut réunir tous les parchemins.",
                str(total), clues, "sum")


def make_rooms(seed: int) -> list[Room]:
    rnd = random.Random(seed)
    return [candle_room(rnd), library_room(rnd), vault_room(rnd)]


def deal(clues: list[str], players: int, seat: int) -> list[str]:
    """Fragments seen by the player sitting at ``seat`` (round-robin)."""
    return [c for i, c in enumerate(clues) if i % players == seat]


def normalize(answer: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFD", answer) if unicodedata.category(c) != "Mn")
    return "".join(c for c in text.upper() if c.isalnum())
