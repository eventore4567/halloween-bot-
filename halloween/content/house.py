"""Rooms and events of the haunted house."""
from __future__ import annotations

import random

ROOMS = [
    dict(name="Le hall d'entrée", emoji="door", text="La porte claque derrière toi. Un lustre se balance tout seul…",
         choices=[("Monter l'escalier", "bat"), ("Ouvrir le placard", "door"), ("Suivre les traces de pas", "eye")]),
    dict(name="La bibliothèque", emoji="book", text="Des livres tombent des étagères. L'un d'eux murmure ton nom.",
         choices=[("Lire le grimoire", "book"), ("Fouiller le bureau", "scroll"), ("Suivre le chat noir", "eye")]),
    dict(name="La cuisine", emoji="cauldron", text="Une marmite bouillonne sur un feu qui n'a pas été allumé.",
         choices=[("Goûter la soupe", "cauldron"), ("Ouvrir le garde-manger", "door"), ("Regarder sous la table", "spider")]),
    dict(name="La salle de bal", emoji="moon", text="Des couples fantômes valsent sur une musique qui grésille.",
         choices=[("Danser avec un fantôme", "ghost_still"), ("Fouiller le piano", "key"), ("Traverser en courant", "lightning")]),
    dict(name="Le grenier", emoji="spider", text="Des toiles partout, et une malle cadenassée dans un coin.",
         choices=[("Forcer la malle", "chest"), ("Écarter les toiles", "web"), ("Regarder par la lucarne", "moon")]),
    dict(name="La cave", emoji="bone", text="Ça sent la terre humide. Quelque chose gratte derrière le mur.",
         choices=[("Creuser le sol", "bone"), ("Ouvrir les tonneaux", "potion_red"), ("Écouter le mur", "eye")]),
    dict(name="La chapelle", emoji="candle", text="Les bougies s'allument une à une à ton passage.",
         choices=[("Prier à l'autel", "candle"), ("Soulever une dalle", "tomb"), ("Sonner la cloche", "lightning")]),
    dict(name="La serre", emoji="mushroom", text="Les plantes se tournent vers toi. Certaines ont des dents.",
         choices=[("Cueillir un champignon", "mushroom"), ("Arracher une mandragore", "frog"), ("Fouiller les pots", "gift")]),
    dict(name="La chambre d'enfant", emoji="ghost_still", text="Un cheval à bascule grince. Une boîte à musique joue toute seule.",
         choices=[("Ouvrir la boîte à musique", "gift"), ("Regarder sous le lit", "eye"), ("Parler à la poupée", "skull")]),
    dict(name="La galerie des portraits", emoji="eye", text="Les yeux des tableaux te suivent. L'un d'eux cligne.",
         choices=[("Décrocher un tableau", "scroll"), ("Toucher le cadre doré", "crown"), ("Fixer le portrait", "eye")]),
]

CRYPT = dict(name="La crypte", emoji="coffin",
             text="Un escalier mène à une crypte scellée. Un coffre géant brille faiblement derrière la grille.")

MONSTERS = [("vampire", "Un vampire jaillit d'un rideau !"), ("zombie", "Un zombie t'agrippe la cheville !"),
            ("werewolf", "Un loup-garou surgit en hurlant !"), ("mummy", "Une momie te barre la route !"),
            ("spider", "Une araignée géante tombe du plafond !")]
TRAPS = ["Une trappe s'ouvre sous tes pieds ! Des bonbons tombent dans le vide…",
         "Un courant d'air glacé souffle ton sac de bonbons…",
         "Un poltergeist te secoue comme un prunier !"]
TREASURES = ["Tu trouves une cachette remplie de bonbons !", "Un fantôme gentil te glisse des bonbons dans la poche.",
             "Un vieux coffret contient des bonbons encore emballés !", "Des bonbons pleuvent du plafond !"]
EMPTY = ["Rien… à part un frisson dans le dos.", "Un chat noir te fixe, puis disparaît.",
         "Tu entends un rire d'enfant. Il n'y a personne.", "Une porte grince toute seule. Rien d'autre."]

# outcome -> base weight; deeper rooms are richer and more dangerous
OUTCOMES = {"treasure": 34, "key": 12, "item": 7, "trap": 14, "monster": 17, "ghost": 8, "empty": 8}
DEPTH = 4  # rooms before the crypt
LIVES = 3


def outcome(depth: int, has_key: bool, rnd=random) -> str:
    weights = dict(OUTCOMES)
    weights["trap"] += 3 * (depth - 1)
    weights["monster"] += 3 * (depth - 1)
    if has_key:
        weights["treasure"] += weights.pop("key")
    keys = list(weights)
    return rnd.choices(keys, weights=[weights[k] for k in keys])[0]


def treasure_amount(depth: int, rnd=random) -> int:
    return int(rnd.randint(18, 36) * (1 + 0.5 * (depth - 1)))


def crypt_amount(bag: int, rnd=random) -> int:
    return rnd.randint(150, 300) + bag // 2
