"""Daily and weekly challenges ("défis").

Every reward goes through :func:`rewards.grant`, which calls :func:`track`:
the reason of the reward counts as one play of that game, the ``stats`` it adds
and the candies it pays are counted too. A challenge is just a counter key with
a goal; each player gets 3 daily and 2 weekly challenges, picked from a seed so
they stay the same all day (or all week).
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Quest:
    qid: str
    text: str
    key: str  # "play:<reason>", "play:any", "stat:<key>" or "candies"
    goal: int
    reward: int
    icon: str
    game: str | None = None  # opener key, for the "play" buttons


DAILY = [
    Quest("d_quiz", "Réponds juste à 6 questions du Grand Frisson", "stat:quiz_right", 6, 160, "skull", "quiz"),
    Quest("d_house", "Explore 2 fois la Maison hantée", "play:maison", 2, 120, "house", "house"),
    Quest("d_race", "Lance 2 courses de balais", "play:course", 2, 100, "witch", "race"),
    Quest("d_ritual", "Accomplis 2 rituels", "play:rituel", 2, 100, "candle", "ritual"),
    Quest("d_reflex", "Joue 3 parties de Réflexe", "play:reflexe", 3, 100, "lightning", "reflex"),
    Quest("d_ouija", "Trouve 3 mots à la Planche Ouija", "stat:ouija_words", 3, 150, "crystal", "ouija"),
    Quest("d_shell", "Gagne 3 manches de Bonneteau", "stat:shell_win", 3, 150, "pumpkin", "shell"),
    Quest("d_memory", "Gagne 1 partie de Mémoire", "stat:memory_win", 1, 120, "eye", "memory"),
    Quest("d_hangman", "Sauve 1 squelette au Pendu", "stat:hangman_win", 1, 120, "bone", "hangman"),
    Quest("d_hunt", "Termine 2 chasses aux fantômes", "play:chasse", 2, 100, "ghost", "hunt"),
    Quest("d_formula", "Tente 1 formule au chaudron", "play:formule", 1, 90, "cauldron", "cauldron"),
    Quest("d_slots", "Joue 5 fois à la Machine hantée", "play:machine", 5, 120, "gem", "slots"),
    Quest("d_motus", "Trouve 1 mot au Motus des ombres", "stat:motus_win", 1, 160, "book", "motus"),
    Quest("d_hilo", "Donne 5 bonnes réponses à Plus ou Moins", "stat:hilo_right", 5, 130, "star", "hilo"),
    Quest("d_fuite", "Franchis 12 obstacles à La Grande Fuite", "stat:run_obstacles", 12, 140, "reaper", "fuite"),
    Quest("d_candies", "Gagne 600 bonbons aujourd'hui", "candies", 600, 150, "candy_bag", None),
    Quest("d_games", "Joue 6 parties, tous jeux confondus", "play:any", 6, 140, "dice", "hub"),
]
WEEKLY = [
    Quest("w_candies", "Gagne 6 000 bonbons cette semaine", "candies", 6000, 1200, "candy_bag", None),
    Quest("w_games", "Joue 40 parties cette semaine", "play:any", 40, 1000, "dice", "hub"),
    Quest("w_quiz", "Réponds juste à 40 questions", "stat:quiz_right", 40, 1000, "skull", "quiz"),
    Quest("w_duel", "Gagne 3 duels contre d'autres membres", "stat:duel_win", 3, 900, "vampire", None),
    Quest("w_quests", "Accomplis 12 défis du jour", "stat:quests_done", 12, 1500, "trophy", None),
    Quest("w_jackpot", "Aligne 5 combinaisons à la Machine hantée", "stat:slots_win", 5, 1000, "gem", "slots"),
]
DAILY_COUNT, WEEKLY_COUNT = 3, 2
ALL_DONE_BONUS = 200  # + one wheel ticket when the 3 daily challenges are claimed

# Reasons of `grant` that mean "one game was played".
GAME_REASONS = {"grand-frisson", "maison", "course", "rituel", "reflexe", "ouija", "bonneteau", "memoire", "pendu",
                "chasse", "formule", "roue", "machine", "motus", "plusoumoins", "duel", "expedition", "fuite"}


def week_key(day: str | None = None) -> str:
    d = dt.date.fromisoformat(day or config.today())
    iso = d.isocalendar()
    return f"W{iso[0]}-{iso[1]:02d}"


def next_monday_ts() -> int:
    now = dt.datetime.now(config.TZ)
    monday = (now + dt.timedelta(days=7 - now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(monday.timestamp())


def daily_quests(g: int, u: int, day: str | None = None) -> list[Quest]:
    return random.Random(f"{g}:{u}:{day or config.today()}").sample(DAILY, DAILY_COUNT)


def weekly_quests(g: int, u: int, week: str | None = None) -> list[Quest]:
    return random.Random(f"{g}:{u}:{week or week_key()}").sample(WEEKLY, WEEKLY_COUNT)


def _active(g, u):
    day, week = config.today(), week_key()
    return [(q, day) for q in daily_quests(g, u, day)] + [(q, week) for q in weekly_quests(g, u, week)]


def progress(store, g, u, quest: Quest, period: str) -> int:
    return store.counter(g, u, "q:" + quest.key, day=period)


def claimed(store, g, u, quest: Quest, period: str) -> bool:
    return store.counter(g, u, "qc:" + quest.qid, day=period) > 0


def track(store, g: int, u: int, reason: str, stats: dict | None, candies: int) -> list[Quest]:
    """Count a reward towards the challenges; return the challenges it just completed."""
    keys = {}
    if reason in GAME_REASONS:
        keys["play:" + reason] = 1
        keys["play:any"] = 1
    for key, amount in (stats or {}).items():
        if amount > 0:
            keys["stat:" + key] = amount
    if candies > 0:
        keys["candies"] = candies
    if not keys:
        return []
    active = _active(g, u)
    done = []
    periods = {period for _q, period in active}
    for period in periods:
        for key, amount in keys.items():
            before = store.counter(g, u, "q:" + key, day=period)
            store.bump(g, u, "q:" + key, amount=amount, day=period)
            for q, p in active:
                if p == period and q.key == key and before < q.goal <= before + amount:
                    done.append(q)
    return done


def claim_all(store, g: int, u: int) -> tuple[int, list[Quest], bool]:
    """Pay every finished, unclaimed challenge. Returns (candies, quests, daily bonus paid)."""
    total, paid = 0, []
    for q, period in _active(g, u):
        if progress(store, g, u, q, period) >= q.goal and store.bump(g, u, "qc:" + q.qid, limit=1, day=period):
            total += store.add_candies(g, u, q.reward, "defi")
            paid.append(q)
            if q.qid.startswith("d_"):
                store.stat_add(g, u, "quests_done", 1)
    bonus = False
    day = config.today()
    if all(claimed(store, g, u, q, day) for q in daily_quests(g, u, day)) \
            and store.bump(g, u, "qc:all", limit=1, day=day):
        total += store.add_candies(g, u, ALL_DONE_BONUS, "defi-bonus")
        store.give_item(g, u, "ticket")
        bonus = True
    if paid:  # weekly "accomplish N daily challenges" counts these claims
        track(store, g, u, "defi", {"quests_done": sum(1 for q in paid if q.qid.startswith("d_"))}, 0)
    return total, paid, bonus
