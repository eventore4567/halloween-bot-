"""Visual identity, shop and Halloween mini-game content."""
import random
ORANGE = 0xF28C28
PURPLE = 0x8753C7

ITEMS = {
    "hat": ("🎃 Chapeau de citrouille", 280, "Une citrouille magique à porter."),
    "cape": ("🦇 Cape de vampire", 650, "Pour traverser la nuit."),
    "lantern": ("🏮 Lanterne spectrale", 900, "Illumine les cryptes."),
    "broom": ("🧹 Balai de sorcière", 1200, "Le transport préféré des sorcières."),
    "crown": ("👑 Couronne maudite", 2500, "L'objet le plus convoité."),
    "key": ("🗝️ Clé du cimetière", 1750, "Une mystérieuse clé ancienne."),
    "bucket": ("🪣 Seau enchanté", 400, "Conserve les meilleurs bonbons."),
    "ring": ("🕷️ Anneau d'araignée", 750, "Un bijou venu de l'obscurité."),
}
QUIZZES = [
    ("Quand fête-t-on Halloween ?", ["31 octobre", "1er novembre", "25 décembre"], 0),
    ("Quel légume est sculpté à Halloween ?", ["Navet", "Citrouille", "Carotte"], 1),
    ("Quel animal représente souvent les vampires ?", ["Chauve-souris", "Pingouin", "Dauphin"], 0),
    ("Comment s'appelle un mort qui marche ?", ["Dragon", "Zombie", "Phénix"], 1),
    ("Quelle créature change à la pleine lune ?", ["Loup-garou", "Sirène", "Licorne"], 0),
    ("Quel accessoire possède souvent une sorcière ?", ["Épée", "Balai", "Skateboard"], 1),
    ("Comment appelle-t-on une momie ?", ["Corps enveloppé de bandelettes", "Vampire", "Lutin"], 0),
    ("Qu'écrit-on sur une citrouille éclairée ?", ["Jack-o'-lantern", "Boo-cat", "Candy-day"], 0),
]
RIDDLES = [
    ("Je peux remplir une pièce sans prendre de place. Qui suis-je ?", ["La lumière", "La pluie", "Un fantôme"], 0),
    ("Je disparais dès que tu dis mon nom. Qui suis-je ?", ["La nuit", "Le silence", "Le brouillard"], 1),
    ("Je te suis quand il fait clair. Qui suis-je ?", ["Une ombre", "Un vampire", "Une bougie"], 0),
    ("J'ai des dents mais je ne mange pas. Qui suis-je ?", ["Un peigne", "Un monstre", "Une clé"], 0),
]
HUNTS = [
    ("👻 Fantôme timide", 40, 70),
    ("🦇 Spectre nocturne", 75, 120),
    ("💀 Esprit du cimetière", 110, 180),
    ("✨ Ombre légendaire", 180, 260),
]
EVENTS = [
    ("🍬 PLUIE DE BONBONS", "Une pluie de bonbons vient d'apparaître !"),
    ("👻 FANTÔME SAUVAGE", "Un fantôme traverse le serveur. Attrape-le !"),
    ("🎃 CITROUILLE MAGIQUE", "Une citrouille lumineuse surgit du brouillard."),
    ("🦇 ESSAIM DE CHAUVES-SOURIS", "Les chauves-souris apportent une récompense."),
]
ACHIEVEMENTS = [
    ("🍬 Premier panier", lambda p: p["candies"] >= 100),
    ("🎃 Collectionneur", lambda p: p["earned"] >= 1000),
    ("👻 Chasseur", lambda p: p["ghosts"] >= 10),
    ("🦇 Exorciste", lambda p: p["ghosts"] >= 50),
    ("🧩 Cerveau hanté", lambda p: p["quizzes"] >= 10),
    ("⚔️ Champion", lambda p: p["duel_wins"] >= 5),
    ("🏆 Légende", lambda p: p["earned"] >= 10000),
    ("💀 Chasseur de boss", lambda p: p["boss_damage"] >= 500),
    ("🕸️ Chanceux", lambda p: p["events_won"] >= 5),
    ("🌾 Jardinier", lambda p: p["harvests"] >= 10),
    ("🏚️ Explorateur", lambda p: p["expeditions"] >= 10),
]
