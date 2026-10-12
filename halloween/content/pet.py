"""Haunted pets: state, decay over time, levels and evolution stages (pure functions, easy to test)."""
from __future__ import annotations

import time

SPECIES = {
    "ghost": dict(name="Fantôme", icon="ghost", color=(225, 235, 255), food="des soupirs en bocal"),
    "bat": dict(name="Chauve-souris", icon="bat", color=(175, 95, 255), food="des moustiques caramélisés"),
    "pumpkin": dict(name="Citrouille", icon="pumpkin_lit", color=(255, 122, 30), food="du terreau ensorcelé"),
    "spider": dict(name="Araignée", icon="spider", color=(90, 255, 120), food="des mouches en gelée"),
    "werewolf": dict(name="Loup-garou", icon="werewolf", color=(255, 60, 170), food="des os à la cannelle"),
}
STAGES = [(1, "Bébé"), (5, "Jeune"), (12, "Adulte"), (20, "Légendaire")]
MAX_LEVEL = 30
HUNGER_PER_HOUR = 4.0
JOY_PER_HOUR = 3.0
FEED_COST = 30
FEED_HUNGER, PLAY_JOY, PET_JOY = 35, 30, 10
PLAY_COOLDOWN, PET_COOLDOWN, LOOT_COOLDOWN = 30 * 60, 10 * 60, 4 * 3600


def xp_for(level: int) -> int:
    """XP needed to go from ``level`` to the next one."""
    return 40 + 25 * level


def stage(level: int) -> tuple[int, str]:
    idx = max(i for i, (lvl, _n) in enumerate(STAGES) if level >= lvl)
    return idx, STAGES[idx][1]


def new_pet(species: str, name: str, now: float | None = None) -> dict:
    now = now or time.time()
    return dict(species=species, name=name[:24], level=1, xp=0, hunger=80.0, joy=80.0, updated=now, born=now)


def decay(pet: dict, now: float | None = None) -> dict:
    """Hunger and joy drop with time (never below 0)."""
    now = now or time.time()
    hours = max(0.0, now - pet["updated"]) / 3600
    pet["hunger"] = max(0.0, pet["hunger"] - HUNGER_PER_HOUR * hours)
    pet["joy"] = max(0.0, pet["joy"] - JOY_PER_HOUR * hours)
    pet["updated"] = now
    return pet


def add_xp(pet: dict, amount: int) -> int:
    """Add XP; returns how many levels were gained."""
    gained = 0
    pet["xp"] += amount
    while pet["level"] < MAX_LEVEL and pet["xp"] >= xp_for(pet["level"]):
        pet["xp"] -= xp_for(pet["level"])
        pet["level"] += 1
        gained += 1
    if pet["level"] >= MAX_LEVEL:
        pet["xp"] = 0
    return gained


def mood(pet: dict) -> float:
    """0 (miserable) to 1 (delighted)."""
    return (pet["hunger"] + pet["joy"]) / 200


def mood_text(pet: dict) -> str:
    if pet["hunger"] < 20:
        return "a l'estomac qui gargouille… il réclame à manger !"
    if pet["joy"] < 20:
        return "s'ennuie à mourir (une deuxième fois). Joue avec lui !"
    m = mood(pet)
    if m > 0.8:
        return "ronronne de bonheur dans le noir."
    if m > 0.5:
        return "flotte tranquillement autour de toi."
    return "te regarde avec de grands yeux tristes."


def loot_amount(pet: dict) -> int:
    """Candies brought back from a night out (every 4 hours), better when the pet is happy."""
    return int((40 + 12 * pet["level"]) * (0.5 + mood(pet)))
