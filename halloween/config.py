"""Game balance, colours and static catalogues."""
from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

try:
    TZ = ZoneInfo(os.getenv("BOT_TIMEZONE", "Europe/Paris"))
except Exception:  # pragma: no cover - tzdata missing
    TZ = dt.timezone.utc

BRAND = "Nuit Hantée"

COLORS = {
    "orange": 0xF7852A,
    "purple": 0x8B52E0,
    "green": 0x5FD35C,
    "red": 0xE23E4C,
    "gold": 0xFFC83D,
    "cyan": 0x4FD8E0,
    "night": 0x2A1650,
}

# --------------------------------------------------------------------------
# Levels
# --------------------------------------------------------------------------
TITLES = [
    (1, "Petit Fantôme"),
    (3, "Chasseur de Bonbons"),
    (6, "Apprenti Sorcier"),
    (10, "Momie Gourmande"),
    (15, "Vampire Noble"),
    (20, "Loup-Garou Alpha"),
    (25, "Liche Ancienne"),
    (32, "Roi Citrouille"),
    (40, "Légende d'Halloween"),
]


def xp_for_next(level: int) -> int:
    return 120 + 60 * (level - 1)


def level_from_xp(xp: int):
    """Return (level, xp_into_level, xp_needed_for_next)."""
    level = 1
    while xp >= xp_for_next(level):
        xp -= xp_for_next(level)
        level += 1
    return level, xp, xp_for_next(level)


def rank_title(level: int) -> str:
    title = TITLES[0][1]
    for lvl, name in TITLES:
        if level >= lvl:
            title = name
    return title


# --------------------------------------------------------------------------
# Daily limits & cooldowns
# --------------------------------------------------------------------------
LIMITS = {
    "quiz": 3,  # « Le Grand Frisson » shows per day
    "memory": 6,
    "hunt": 6,
    "hangman": 6,
    "cauldron": 5,
    "house": 5,
    "race": 6,
    "ritual": 6,
    "reflex": 8,
    "ouija": 5,
    "shell": 6,
    "slots": 15,
    "motus": 3,
    "hilo": 6,
    "maze": 4,
    "connect4": 5,
    "roulette": 8,
    "escape": 3,
    "gift_out": 2000,  # max candies a member can give per day
}
WHEEL_COOLDOWN = 4 * 3600

DAILY_BASE = 150
DAILY_STREAK_STEP = 30
DAILY_STREAK_MAX = 7

# --------------------------------------------------------------------------
# Quiz levels
# --------------------------------------------------------------------------
QUIZ_LEVELS = {
    1: dict(key="facile", name="Facile", emoji="pumpkin", reward=(15, 30), xp=8, time=25,
            style="success"),
    2: dict(key="moyen", name="Moyen", emoji="ghost", reward=(30, 60), xp=12, time=25,
            style="primary"),
    3: dict(key="difficile", name="Difficile", emoji="pumpkin_angry", reward=(60, 110), xp=18, time=22,
            style="secondary"),
    4: dict(key="infernal", name="Infernal", emoji="demon", reward=(110, 200), xp=26, time=20,
            style="danger"),
    5: dict(key="cauchemar", name="CAUCHEMAR", emoji="skull_fire", reward=(200, 400), xp=40, time=18,
            style="danger"),
}

# --------------------------------------------------------------------------
# Shop
# --------------------------------------------------------------------------
SHOP = {
    "joker": dict(name="Joker 50/50", emoji="joker", price=120,
                  desc="Retire deux mauvaises réponses au quiz."),
    "shield": dict(name="Bouclier de série", emoji="shield", price=150,
                   desc="Efface une erreur au Grand Frisson."),
    "ticket": dict(name="Ticket de roue", emoji="wheel", price=220,
                   desc="Un tour de roue en plus, sans attendre."),
    "scroll": dict(name="Ticket du Grand Frisson", emoji="scroll", price=260,
                   desc="Une émission de quiz en plus aujourd'hui."),
    "luck": dict(name="Philtre de fortune", emoji="potion_gold", price=650,
                 desc="Tous tes gains de bonbons ×2 pendant 30 min."),
    "booster": dict(name="Booster de cartes", emoji="gift", price=250,
                    desc="Une carte de monstre aléatoire."),
    "amulet": dict(name="Amulette anti-sort", emoji="gem", price=300,
                   desc="Bloque le prochain mauvais sort lancé contre toi."),
}
CURSE_COST = 60
CURSE_COOLDOWN = 3600
CURSE_PROTECTION = 2 * 3600
CURSE_SUCCESS = 0.6
TITLES_SHOP = {
    "t_glouton": dict(name="Glouton de Bonbons", price=1000),
    "t_farceur": dict(name="Fantôme Farceur", price=1200),
    "t_chasseur": dict(name="Chasseur de Vampires", price=1800),
    "t_reine": dict(name="Reine des Citrouilles", price=2500),
    "t_roi": dict(name="Seigneur des Ténèbres", price=2500),
    "t_legende": dict(name="Terreur Absolue", price=10000),
}
CARD_THEMES = {
    "orange": dict(name="Citrouille", price=0, colors=((255, 150, 50), (120, 40, 10))),
    "purple": dict(name="Sortilège", price=800, colors=((176, 110, 255), (50, 20, 100))),
    "green": dict(name="Poison", price=800, colors=((120, 230, 110), (20, 80, 40))),
    "red": dict(name="Sang", price=800, colors=((255, 90, 100), (90, 10, 30))),
    "gold": dict(name="Trésor", price=1500, colors=((255, 214, 90), (110, 70, 10))),
    "cyan": dict(name="Spectre", price=1500, colors=((120, 240, 240), (20, 70, 100))),
}

# --------------------------------------------------------------------------
# Wheel of fortune segments (weight, kind, value, label, emoji)
# --------------------------------------------------------------------------
WHEEL = [
    dict(kind="candy", value=60, label="60 bonbons", emoji="candy", weight=24, color=(247, 133, 36)),
    dict(kind="candy", value=120, label="120 bonbons", emoji="candy", weight=20, color=(139, 82, 224)),
    dict(kind="nothing", value=0, label="Citrouille pourrie", emoji="pumpkin_angry", weight=12, color=(70, 50, 90)),
    dict(kind="candy", value=250, label="250 bonbons", emoji="candy_bag", weight=12, color=(95, 211, 92)),
    dict(kind="item", value="joker", label="Joker 50/50", emoji="joker", weight=10, color=(84, 166, 255)),
    dict(kind="xp", value=120, label="120 XP", emoji="star", weight=10, color=(255, 120, 190)),
    dict(kind="item", value="booster", label="Booster de cartes", emoji="gift", weight=8, color=(226, 62, 76)),
    dict(kind="candy", value=1000, label="JACKPOT 1000", emoji="crown", weight=4, color=(255, 200, 61)),
]


def today(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(TZ)
    return now.astimezone(TZ).strftime("%Y-%m-%d")


def next_midnight_ts(now: dt.datetime | None = None) -> int:
    now = (now or dt.datetime.now(TZ)).astimezone(TZ)
    tomorrow = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(tomorrow.timestamp())


def fmt(n) -> str:
    """French thousands separator: 12 345."""
    n = int(n)
    return f"{n:,}".replace(",", " ")


def short(n) -> str:
    """Compact number: 12 345, 45,2 k, 1,3 M, 2 Md."""
    n = float(n)
    for unit, div, floor in (("Md", 1e9, 1e9), ("M", 1e6, 1e6), ("k", 1e3, 1e5)):
        if abs(n) >= floor:
            return f"{n / div:.1f}".rstrip("0").rstrip(".").replace(".", ",") + f"\u202f{unit}"
    return fmt(n)


# --------------------------------------------------------------------------
# Achievements: (key, name, description, emoji, measured value, goal, reward)
# --------------------------------------------------------------------------
ACHIEVEMENTS = [
    ("first_quiz", "Premier frisson", "Réussir une question de quiz", "crystal", "quiz_right", 1, 50),
    ("quiz_50", "Érudit des ténèbres", "50 bonnes réponses au quiz", "book", "quiz_right", 50, 300),
    ("quiz_250", "Oracle maudit", "250 bonnes réponses au quiz", "crystal", "quiz_right", 250, 1000),
    ("streak_10", "Série infernale", "10 bonnes réponses d'affilée", "fire", "quiz_best_streak", 10, 400),
    ("memory_1", "Mémoire d'outre-tombe", "Gagner une partie de mémoire", "eye", "memory_win", 1, 100),
    ("memory_10", "Mémoire éternelle", "Gagner 10 parties de mémoire", "eye", "memory_win", 10, 500),
    ("hunt_300", "Pilleur de tombes", "Encaisser 300 bonbons à la chasse", "tomb", "hunt_best", 300, 300),
    ("hangman_5", "Sauveur de squelettes", "Gagner 5 parties de pendu", "skull", "hangman_win", 5, 300),
    ("house_5", "Explorateur", "Sortir 5 fois vivant de la maison hantée", "house", "house_escape", 5, 300),
    ("crypt_1", "Pilleur de crypte", "Ouvrir la crypte de la maison hantée", "coffin", "crypt", 1, 400),
    ("duel_1", "Premier sang", "Gagner un duel", "fang", "duel_win", 1, 100),
    ("duel_10", "Maître duelliste", "Gagner 10 duels", "vampire", "duel_win", 10, 600),
    ("boss_1", "Tueur de citrouille", "Vaincre le Roi Citrouille", "pumpkin_angry", "boss_win", 1, 300),
    ("drops_5", "Main rapide", "Attraper 5 apparitions", "lightning", "drops", 5, 250),
    ("potions_1", "Apprenti alchimiste", "Déchiffrer une formule", "cauldron", "potions", 1, 100),
    ("boosters_10", "Collectionneur", "Ouvrir 10 boosters", "gift", "boosters", 10, 300),
    ("cards_24", "Collection complète", "Posséder les 24 cartes", "crown", "cards", 24, 500),
    ("jackpot", "Jackpot !", "Toucher le jackpot de la roue", "wheel", "jackpot", 1, 200),
    ("gift_1", "Cœur sur la main", "Offrir des bonbons", "heart", "gifts", 1, 100),
    ("calendar_10", "Fidèle d'octobre", "Ouvrir 10 cases du calendrier", "gift", "calendar", 10, 400),
    ("pumpkin_1000", "Jardinier hanté", "Donner 1 000 bonbons à la citrouille géante", "pumpkin_lit", "pumpkin_fed",
     1000, 300),
    ("daily_7", "Fidèle à la nuit", "7 jours de coffre d'affilée", "chest", "streak", 7, 400),
    ("level_10", "Monstre confirmé", "Atteindre le niveau 10", "star", "level", 10, 500),
    ("level_25", "Liche ancienne", "Atteindre le niveau 25", "gem", "level", 25, 1500),
    ("earned_10k", "Sac plein", "Gagner 10 000 bonbons au total", "candy_bag", "earned", 10_000, 500),
    ("earned_100k", "Roi des bonbons", "Gagner 100 000 bonbons au total", "crown", "earned", 100_000, 3000),
    ("exp_10", "Chef d'expédition", "Réussir 10 expéditions", "key", "exp_win", 10, 800),
    ("show_top", "Maître du Grand Frisson", "Gravir les 12 marches du Grand Frisson", "skull_fire", "show_top", 1, 1500),
    ("formula_10", "Grand alchimiste", "Déchiffrer 10 formules", "potion_purple", "potions", 10, 400),
    ("ouija_perfect", "Médium", "Réussir une séance Ouija parfaite", "crystal", "ouija_best", 3, 300),
    ("ouija_25", "Voix de l'au-delà", "Trouver 25 mots à la planche Ouija", "candle", "ouija_words", 25, 450),
    ("shell_perfect", "Œil de lynx", "Gagner les 3 manches du Bonneteau", "pumpkin_lit", "shell_best", 3, 300),
    ("slots_jackpot", "Jackpot hanté", "Aligner trois couronnes à la Machine hantée", "crown", "slots_jackpot", 1, 500),
    ("motus_5", "Linguiste des ombres", "Trouver 5 mots au Motus des ombres", "book", "motus_win", 5, 400),
    ("hilo_6", "Devin", "Enchaîner 6 bonnes réponses à Plus ou Moins", "star", "hilo_best", 6, 400),
    ("quests_20", "Chasseur de défis", "Accomplir 20 défis du jour", "scroll", "quests_done", 20, 600),
    ("versus_5", "Roi des défis", "Gagner 5 défis en direct (/defi)", "crown", "versus_win", 5, 500),
    ("maze_5", "Fil d'Ariane", "S'échapper 5 fois du Labyrinthe hanté", "key", "maze_escape", 5, 450),
    ("c4_5", "Stratège des citrouilles", "Gagner 5 parties de Puissance 4", "pumpkin_lit", "c4_win", 5, 450),
    ("pet_12", "Dresseur de l'au-delà", "Faire grandir son familier jusqu'au niveau 12", "heart", "pet_level", 12, 500),
    ("roulette_5", "Estomac d'acier", "Boire 5 fioles saines à la Roulette des potions", "potion_green", "roulette_best", 5, 400),
    ("escape_3", "Maître de l'évasion", "S'échapper 3 fois de la crypte en équipe (/escape)", "key", "escape_win", 3, 500),
    ("trades_3", "Marchand d'âmes", "Conclure 3 échanges de cartes (/echange)", "gift", "trades", 3, 400),
]


# --------------------------------------------------------------------------
# « Le Grand Frisson » (quiz TV show)
# --------------------------------------------------------------------------
SHOW_LADDER = [20, 40, 70, 110, 160, 230, 320, 440, 600, 800, 1100, 1500]
SHOW_SAFE = {5, 9}  # 1-based rungs that are kept even after a wrong answer
SHOW_LEVELS = [1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 5]
SHOW_SHADOW_RUNGS = {3, 6, 9}  # "who hides in the shadows?" video rounds


def show_safe_amount(correct_answers: int) -> int:
    """What a player keeps after a wrong answer, having answered ``correct_answers`` right."""
    kept = 0
    for rung in sorted(SHOW_SAFE):
        if correct_answers >= rung:
            kept = SHOW_LADDER[rung - 1]
    return kept


# --------------------------------------------------------------------------
# October calendar (one box per day, 1 → 31 October)
# --------------------------------------------------------------------------
def calendar_reward(day: int) -> dict:
    """What box ``day`` of October contains."""
    if day == 31:
        return dict(candies=1500, xp=150, item="booster", legendary=True, emoji="crown", label="LE GRAND JACKPOT")
    if day == 13:
        return dict(candies=0, xp=40, cursed=True, emoji="skull_fire", label="La case maudite")
    if day % 7 == 0:
        return dict(candies=80 + 12 * day, xp=30, item="booster", emoji="gift", label="Bonbons + booster")
    if day % 5 == 0:
        return dict(candies=80 + 12 * day, xp=30, item="ticket", emoji="wheel", label="Bonbons + ticket de roue")
    return dict(candies=60 + 10 * day, xp=15 + day, emoji="candy", label="Sac de bonbons")


# --------------------------------------------------------------------------
# Giant pumpkin (server-wide goal fed with candies)
# --------------------------------------------------------------------------
PUMPKIN_STAGES = [
    (0, "Graine maudite"),
    (2_000, "Pousse tordue"),
    (6_000, "Petite citrouille"),
    (15_000, "Grosse citrouille"),
    (35_000, "Citrouille géante"),
    (80_000, "Citrouille colossale"),
    (150_000, "CITROUILLE MONSTRUEUSE"),
]
PUMPKIN_FEEDS = [50, 200, 500]


def pumpkin_stage(total: int) -> int:
    stage = 0
    for i, (threshold, _) in enumerate(PUMPKIN_STAGES):
        if total >= threshold:
            stage = i
    return stage
