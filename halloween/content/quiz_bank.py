"""Quiz question bank.

Format: one question per line, ``question | good answer | wrong | wrong | wrong``.
``@N`` switches the difficulty level (1 to 5), ``# Name`` switches the category.
Questions are parsed once at import; ids are stable hashes of the text so
"already seen" tracking survives edits elsewhere in the file.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from . import quiz_text, quiz_text_hard

RAW = "\n".join(quiz_text.RAW_PARTS + quiz_text_hard.RAW_PARTS)


@dataclass(frozen=True)
class Question:
    qid: str
    level: int
    category: str
    text: str
    answer: str
    wrong: tuple

    def shuffled(self, rnd: random.Random | None = None):
        rnd = rnd or random
        options = [self.answer, *self.wrong]
        rnd.shuffle(options)
        return options, options.index(self.answer)


def parse(raw: str) -> list[Question]:
    level, category = 1, "Divers"
    out: list[Question] = []
    seen = set()
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith("@"):
            level = int(line[1:])
            continue
        if line.startswith("#"):
            category = line[1:].strip()
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 5 or not all(parts):
            raise ValueError(f"quiz line {lineno} malformed: {line!r}")
        text, answer, *wrong = parts
        if len({answer.lower(), *(w.lower() for w in wrong)}) != 4:
            raise ValueError(f"quiz line {lineno} has duplicate answers: {line!r}")
        key = text.lower()
        if key in seen:
            raise ValueError(f"quiz line {lineno} duplicates a question: {text!r}")
        seen.add(key)
        qid = hashlib.sha1(text.encode()).hexdigest()[:10]
        out.append(Question(qid, level, category, text, answer, tuple(wrong)))
    return out


QUESTIONS = parse(RAW)
BY_LEVEL: dict[int, list[Question]] = {}
for _q in QUESTIONS:
    BY_LEVEL.setdefault(_q.level, []).append(_q)
BY_ID = {q.qid: q for q in QUESTIONS}
TOTAL = len(QUESTIONS)


def pick(level: int, seen: set, rnd: random.Random | None = None) -> tuple[Question, bool]:
    """Pick an unseen question. Returns (question, pool_was_reset)."""
    rnd = rnd or random
    pool = BY_LEVEL[level]
    fresh = [q for q in pool if q.qid not in seen]
    if fresh:
        return rnd.choice(fresh), False
    return rnd.choice(pool), True
