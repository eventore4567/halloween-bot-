"""Static content for the mini-games."""
from __future__ import annotations

import hashlib
import itertools
import random
import unicodedata

# ---------------------------------------------------------------------------
# Hangman
# ---------------------------------------------------------------------------
HANGMAN = [
    ("CITROUILLE", "On la creuse pour en faire une lanterne"),
    ("FANTÔME", "Il traverse les murs"),
    ("SORCIÈRE", "Elle vole sur un balai"),
    ("VAMPIRE", "Il a peur de l'ail"),
    ("SQUELETTE", "Que des os !"),
    ("CHAUDRON", "On y prépare les potions"),
    ("CIMETIÈRE", "Rempli de tombes"),
    ("ARAIGNÉE", "Huit pattes et une toile"),
    ("CHAUVE-SOURIS", "Elle dort la tête en bas"),
    ("LOUP-GAROU", "Il se transforme à la pleine lune"),
    ("MOMIE", "Enveloppée de bandelettes"),
    ("ZOMBIE", "Un mort-vivant affamé"),
    ("CERCUEIL", "Le lit du vampire"),
    ("GRIMOIRE", "Le livre des sortilèges"),
    ("BALAI", "Le véhicule des sorcières"),
    ("BONBON", "On en récolte en frappant aux portes"),
    ("POTION", "Breuvage magique"),
    ("ÉPOUVANTAIL", "Il effraie les corbeaux"),
    ("CORBEAU", "Oiseau noir de mauvais augure"),
    ("HIBOU", "Il fait hou-hou la nuit"),
    ("LANTERNE", "Elle éclaire la nuit"),
    ("TRANSYLVANIE", "Le pays de Dracula"),
    ("FRANKENSTEIN", "Le savant qui créa une créature"),
    ("MALÉDICTION", "Un sort qui porte malheur"),
    ("SORTILÈGE", "Formule magique"),
    ("NÉCROMANCIEN", "Il parle aux morts"),
    ("ECTOPLASME", "Substance des fantômes"),
    ("POLTERGEIST", "Esprit qui déplace les objets"),
    ("GARGOUILLE", "Statue monstrueuse des cathédrales"),
    ("CRYPTE", "Caveau sous une église"),
    ("PLEINE LUNE", "Elle réveille les loups-garous"),
    ("TOILE", "Le piège de l'araignée"),
    ("MANDRAGORE", "Plante qui hurle quand on l'arrache"),
    ("ALCHIMISTE", "Il veut changer le plomb en or"),
    ("BANSHEE", "Elle hurle pour annoncer la mort"),
    ("FAUCHEUSE", "Elle porte une grande faux"),
    ("TOUSSAINT", "Le lendemain d'Halloween"),
    ("DÉGUISEMENT", "On le porte pour faire peur"),
    ("HURLEMENT", "Le cri du loup"),
    ("OSSEMENTS", "Restes d'un squelette"),
    ("PIERRE TOMBALE", "Elle porte un nom et deux dates"),
    ("CHAT NOIR", "Il porterait malheur"),
    ("BOULE DE CRISTAL", "La voyante y lit l'avenir"),
    ("MAISON HANTÉE", "Personne n'ose y entrer"),
    ("FEU FOLLET", "Petite flamme des marais"),
    ("DRACULA", "Le comte le plus célèbre"),
    ("GOBELIN", "Petite créature farceuse et rusée"),
    ("TÉNÈBRES", "Obscurité totale"),
    ("SABBAT", "Assemblée nocturne de sorcières"),
    ("EXORCISTE", "Il chasse les démons"),
]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Cauldron
# ---------------------------------------------------------------------------
INGREDIENTS = [
    dict(key="eye", name="Œil de triton", emoji="eye"),
    dict(key="frog", name="Bave de crapaud", emoji="frog"),
    dict(key="bone", name="Os de squelette", emoji="bone"),
    dict(key="mushroom", name="Champignon vénéneux", emoji="mushroom"),
    dict(key="spider", name="Araignée velue", emoji="spider"),
    dict(key="bat", name="Aile de chauve-souris", emoji="bat"),
    dict(key="feather", name="Plume de corbeau", emoji="feather"),
    dict(key="fang", name="Croc de vampire", emoji="fang"),
]
ING = {i["key"]: i for i in INGREDIENTS}

POTIONS = [
    dict(key="knowledge", name="Élixir du savoir", emoji="potion_blue", effect="quiz5",
         desc="**+5 questions** de quiz aujourd'hui"),
    dict(key="fortune", name="Philtre de fortune", emoji="potion_gold", effect="luck30",
         desc="Tous tes gains de bonbons **×2** pendant 30 min"),
    dict(key="souls", name="Potion des âmes", emoji="potion_purple", effect="souls",
         desc="**1 heure** de production du manoir, tout de suite"),
    dict(key="blood", name="Élixir de sang", emoji="potion_red", effect="candy",
         desc="**+180** bonbons instantanés"),
    dict(key="wisdom", name="Philtre de sagesse", emoji="potion_green", effect="xp60",
         desc="**XP ×2** pendant 1 heure"),
    dict(key="joker", name="Brume de vérité", emoji="crystal", effect="joker2",
         desc="**2 jokers 50/50** pour le quiz"),
    dict(key="shield", name="Sérum spectral", emoji="shield", effect="shield",
         desc="**1 bouclier** qui protège ta série au quiz"),
    dict(key="wheel", name="Nectar du destin", emoji="wheel", effect="ticket",
         desc="**1 ticket** de roue du destin"),
]
POTION = {p["key"]: p for p in POTIONS}

FAILS = [
    ("La potion fait « pschitt » et devient une soupe tiède.", 8),
    ("Le chaudron explose ! Tu as les sourcils roussis…", 0),
    ("Ça sent le vieux chaussette. Personne n'en voudra.", 5),
    ("La mixture devient rose et se met à chanter faux.", 10),
    ("Un crapaud saute du chaudron et s'enfuit avec ta cuillère.", 0),
    ("La potion gèle instantanément. Bizarre…", 6),
    ("Une fumée verte forme le mot « RATÉ ».", 4),
]


def all_pairs():
    keys = [i["key"] for i in INGREDIENTS]
    return [tuple(sorted(p)) for p in itertools.combinations(keys, 2)]


def daily_recipes(guild_id: int, day: str) -> dict[tuple, str]:
    """Each server gets its own 8 secret pairs, reshuffled at midnight."""
    seed = int(hashlib.sha256(f"{guild_id}:{day}:cauldron".encode()).hexdigest()[:12], 16)
    rnd = random.Random(seed)
    pairs = all_pairs()
    rnd.shuffle(pairs)
    return {pairs[i]: POTIONS[i]["key"] for i in range(len(POTIONS))}


# ---------------------------------------------------------------------------
# Collectible cards
# ---------------------------------------------------------------------------
RARITIES = {
    "C": dict(name="Commune", stars=1, weight=60, refund=40, color=(150, 160, 190), color2=(80, 86, 110)),
    "R": dict(name="Rare", stars=2, weight=27, refund=90, color=(90, 170, 255), color2=(30, 70, 160)),
    "E": dict(name="Épique", stars=3, weight=10, refund=200, color=(196, 120, 255), color2=(90, 30, 170)),
    "L": dict(name="Légendaire", stars=4, weight=3, refund=500, color=(255, 200, 70), color2=(190, 90, 10)),
}

CARDS = [
    dict(key="c_pumpkin", name="Citrouille Farceuse", emoji="pumpkin", rarity="C",
         flavor="Elle rit toute seule dans le potager."),
    dict(key="c_bat", name="Chauve-souris Pipelette", emoji="bat", rarity="C",
         flavor="Elle ne se tait jamais, même la tête en bas."),
    dict(key="c_spider", name="Araignée Tricoteuse", emoji="spider", rarity="C",
         flavor="Ses toiles font des pulls très aérés."),
    dict(key="c_frog", name="Crapaud Baveux", emoji="frog", rarity="C",
         flavor="Ingrédient préféré des sorcières."),
    dict(key="c_mushroom", name="Champignon Grincheux", emoji="mushroom", rarity="C",
         flavor="Ne le mange surtout pas."),
    dict(key="c_candle", name="Bougie Hantée", emoji="candle", rarity="C",
         flavor="Elle se rallume toute seule à minuit."),
    dict(key="c_bone", name="Os Baladeur", emoji="bone", rarity="C",
         flavor="Il cherche encore son squelette."),
    dict(key="c_eye", name="Œil Fouineur", emoji="eye", rarity="C",
         flavor="Il voit tout. Absolument tout."),
    dict(key="c_cookie", name="Biscuit Maudit", emoji="cookie", rarity="C",
         flavor="Croustillant à l'extérieur, hanté à l'intérieur."),
    dict(key="c_tomb", name="Pierre Tombale", emoji="tomb", rarity="C",
         flavor="Ci-gît un joueur qui a raté le quiz."),
    dict(key="r_ghost", name="Fantôme Timide", emoji="ghost_still", rarity="R",
         flavor="Il dit « bouh » tout bas, pour ne déranger personne."),
    dict(key="r_zombie", name="Zombie Gourmand", emoji="zombie", rarity="R",
         flavor="Il préfère les bonbons aux cerveaux."),
    dict(key="r_mummy", name="Momie Frileuse", emoji="mummy", rarity="R",
         flavor="Elle rajoute une bandelette chaque hiver."),
    dict(key="r_soul", name="Âme Errante", emoji="soul", rarity="R",
         flavor="Elle cherche le chemin du manoir."),
    dict(key="r_coffin", name="Cercueil Ronfleur", emoji="coffin", rarity="R",
         flavor="On l'entend ronfler à trois tombes de là."),
    dict(key="r_cauldron", name="Chaudron Glouton", emoji="cauldron", rarity="R",
         flavor="Il avale tous les ingrédients… et la louche."),
    dict(key="r_moon", name="Lune Sanglante", emoji="moon", rarity="R",
         flavor="Quand elle se lève, les loups hurlent."),
    dict(key="e_witch", name="Morgane la Sorcière", emoji="witch", rarity="E",
         flavor="Patronne de la boutique. Ne marchande pas."),
    dict(key="e_werewolf", name="Loup-garou Alpha", emoji="werewolf", rarity="E",
         flavor="Chef de meute, terreur des nuits de pleine lune."),
    dict(key="e_vampire", name="Comte Vampire", emoji="vampire", rarity="E",
         flavor="Il ne boit que du jus de tomate. Paraît-il."),
    dict(key="e_skull", name="Crâne Ardent", emoji="skull_fire", rarity="E",
         flavor="Ses flammes violettes ne s'éteignent jamais."),
    dict(key="l_reaper", name="La Faucheuse", emoji="reaper", rarity="L",
         flavor="Elle vient toujours à l'heure."),
    dict(key="l_demon", name="Belzébonbon", emoji="demon", rarity="L",
         flavor="Le démon qui a inventé la carie."),
    dict(key="l_king", name="Le Roi Citrouille", emoji="pumpkin_angry", rarity="L",
         flavor="Souverain absolu de la Nuit Hantée."),
]
CARD = {c["key"]: c for c in CARDS}
COLLECTION_BONUS = 5000


def draw_card(rnd: random.Random | None = None) -> dict:
    rnd = rnd or random
    rarity = rnd.choices(list(RARITIES), weights=[r["weight"] for r in RARITIES.values()])[0]
    return rnd.choice([c for c in CARDS if c["rarity"] == rarity])


# ---------------------------------------------------------------------------
# Memory game symbols
# ---------------------------------------------------------------------------
MEMORY_SYMBOLS = ["pumpkin", "ghost_still", "bat", "skull", "witch", "vampire", "spider", "candy",
                  "zombie", "mummy", "eye", "potion_green", "cauldron", "moon", "frog", "coffin"]

# ---------------------------------------------------------------------------
# Drops
# ---------------------------------------------------------------------------
DROP_SCENES = [
    dict(title="Un sac de bonbons tombe du ciel !", emoji="candy_bag", button="Attraper le sac", reward=(80, 220)),
    dict(title="Une citrouille géante roule dans le salon !", emoji="pumpkin_lit", button="Ouvrir la citrouille",
         reward=(60, 200)),
    dict(title="Un coffre maudit vient d'apparaître !", emoji="chest", button="Forcer le coffre", reward=(120, 300)),
    dict(title="Un fantôme distribue des bonbons !", emoji="ghost", button="Tendre la main", reward=(70, 190)),
    dict(title="Une chauve-souris lâche son butin !", emoji="bat", button="Rattraper le butin", reward=(60, 180)),
]
