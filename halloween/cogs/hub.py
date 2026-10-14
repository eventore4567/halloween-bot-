"""/jeux — the haunted arcade hub, and /aide — the guide."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content import quiz_bank
from ..emojis import E
from ..ui import GameView, Panel, nav

GAMES = [
    ("quiz", "Le Grand Frisson", "skull", f"Le jeu télé : 12 questions, 3 jokers, manches vidéo ({quiz_bank.TOTAL} questions)"),
    ("manor", "Expéditions", "key", "Envoie tes cartes de monstres en mission"),
    ("cauldron", "La Formule", "cauldron", "Déchiffre le code secret du chaudron"),
    ("wheel", "Roue du destin", "wheel", "Un tour gratuit toutes les 4 heures"),
    ("cards", "Cartes maudites", "gift", "Collectionne les 24 monstres"),
    ("house", "Maison hantée", "house", "4 pièces, 3 bougies, une crypte au trésor"),
    ("race", "Course de balais", "witch", "Parie sur la sorcière la plus rapide"),
    ("memory", "Mémoire d'outre-tombe", "eye", "Retrouve les 8 paires"),
    ("hunt", "Chasse aux fantômes", "ghost", "Creuse les tombes… évite la Faucheuse"),
    ("hangman", "Le Pendu", "skull", "Sauve le squelette lettre par lettre"),
    ("ritual", "Le Rituel", "candle", "Mémorise la formule maudite et répète-la"),
    ("ouija", "La Planche Ouija", "crystal", "L'esprit épelle un mot en vidéo : devine lequel"),
    ("shell", "Le Bonneteau", "pumpkin", "Suis le bonbon sous les citrouilles qui se mélangent"),
    ("slots", "Machine hantée", "gem", "Tire le levier, aligne trois monstres"),
    ("motus", "Motus des ombres", "book", "Trouve le mot d'Halloween en 6 essais"),
    ("hilo", "Plus ou Moins", "star", "Devine la carte suivante, fais grossir le pot"),
    ("reflex", "Réflexe du fantôme", "lightning", "Clique dès qu'il apparaît"),
    ("maze", "Labyrinthe hanté", "key", "Trouve la clé et la sortie, le fantôme te traque"),
    ("fuite", "La Grande Fuite", "reaper", "Runner 2D : saute, glisse, frappe, la Faucheuse te suit"),
    ("pet", "Familier hanté", "bat", "Adopte un monstre, nourris-le, fais-le évoluer"),
    ("roulette", "Roulette des potions", "potion_green", "Une fiole sur six est empoisonnée"),
    ("traitre", "Le Traître", "vampire", "4 à 12 joueurs : démasquez les vampires cachés parmi vous"),
    ("escape", "Escape Game", "lock", "En équipe : 3 salles, indices secrets, 10 minutes"),
    ("film", "Le Film de ta Nuit", "eye", "Ta saison d'Halloween en film animé"),
    ("connect4", "Puissance 4 maudit", "pumpkin_lit", "Aligne 4 citrouilles contre la Sorcière"),
    ("chateau", "Le Château hanté", "house", "Ton serveur en château : qui est où, où rôde le Spectre"),
    ("defis", "Défis du jour", "scroll", "3 défis par jour, 2 par semaine, gros bonus"),
    ("daily", "Coffre du jour", "chest", "Ta récompense quotidienne + série"),
    ("calendar", "Calendrier d'octobre", "gift", "Une case par jour, jackpot le 31"),
    ("giant", "Citrouille géante", "pumpkin_lit", "Tout le serveur la nourrit ensemble"),
    ("shop", "La Boutique", "witch", "Jokers, potions, titres et thèmes"),
    ("top", "Le Panthéon", "trophy", "Les classements du serveur"),
    ("profile", "Mon profil", "pumpkin_lit", "Ta carte de chasseur et tes quotas"),
    ("trophies", "Succès", "medal1", f"{len(config.ACHIEVEMENTS)} trophées à débloquer"),
]

GAME = {key: (name, icon, desc) for key, name, icon, desc in GAMES}
# Every game also has its own slash command.
COMMAND = {"quiz": "quiz", "ouija": "ouija", "shell": "bonneteau", "motus": "motus", "hangman": "pendu",
           "slots": "machine", "roulette": "roulette", "hilo": "plusoumoins", "race": "course", "wheel": "roue",
           "hunt": "chasse", "memory": "memoire", "ritual": "rituel", "reflex": "reflexe", "maze": "labyrinthe", "fuite": "fuite",
           "cauldron": "formule", "escape": "escape", "traitre": "traitre", "house": "maison", "manor": "expedition", "cards": "cartes",
           "connect4": "puissance4", "pet": "familier", "defis": "defis", "chateau": "chateau", "daily": "quotidien",
           "calendar": "calendrier", "giant": "citrouille", "film": "film", "profile": "profil",
           "trophies": "succes", "top": "classement", "shop": "boutique"}

# The select menu holds 25 options at most: games are grouped by category.
CATEGORIES = [
    ("quiz", "Quiz & vidéo", "skull", ["quiz", "ouija", "shell", "motus", "hangman"]),
    ("luck", "Hasard & mises", "dice", ["slots", "roulette", "hilo", "race", "wheel", "hunt"]),
    ("brain", "Mémoire & réflexes", "eye", ["fuite", "memory", "ritual", "reflex", "maze", "cauldron"]),
    ("adventure", "Aventure & collection", "key", ["traitre", "escape", "house", "manor", "cards", "connect4"]),
    ("night", "Rendez-vous de la nuit", "moon", ["chateau", "pet", "defis", "daily", "calendar", "giant"]),
    ("me", "Ma progression", "trophy", ["film", "profile", "trophies", "top", "shop"]),
]
CATEGORY = {c[0]: c for c in CATEGORIES}

TIPS = [
    "Au Grand Frisson, les marches 5 et 9 sont des paliers : tu ne redescends jamais en dessous.",
    "Plus tes monstres sont rares, plus tes expéditions réussissent.",
    "Le Philtre de fortune double TOUS tes gains de bonbons pendant 30 minutes.",
    "Le murmure du fantôme se trompe parfois… surtout sur les questions difficiles.",
    "À La Formule, commence par tester des ingrédients différents pour éliminer des pistes.",
    "Ne rate pas un jour de coffre : la série monte jusqu'à 7 jours.",
    "Défie un ami avec /duel et mise tes bonbons !",
    "Garde l'œil sur le salon des apparitions : le premier qui clique gagne.",
    "À La Grande Fuite, regarde la hauteur de l'obstacle : en bas on saute, en haut on glisse, un monstre on le frappe.",
]


class HubView(GameView):
    banner_key = "hub"
    kicker = "NUIT HANTÉE"

    def __init__(self, bot, interaction, page="home"):
        super().__init__(bot, interaction, timeout=600)
        self.page = page

    async def interaction_check(self, interaction):
        return True  # anyone can use the hub; others get their own panel

    def build(self) -> Panel:
        p = Panel("orange").banner(self.banner_key)
        cat = CATEGORY.get(self.page[4:]) if self.page.startswith("cat:") else None
        if self.page == "guide":
            self._guide(p)
        elif cat:
            self._category(p, cat)
        else:
            self._home(p)
        p.sep()
        if cat:
            select = discord.ui.Select(placeholder=f"Choisis un jeu : {cat[1]}…", options=[
                discord.SelectOption(label=GAME[k][0], value=k, emoji=E.partial(GAME[k][1]), description=GAME[k][2][:100])
                for k in cat[3]])
            select.callback = self.on_pick
        else:
            select = discord.ui.Select(placeholder="Choisis une catégorie de jeux…", options=[
                discord.SelectOption(label=name, value=key, emoji=E.partial(icon),
                                     description=" · ".join(GAME[k][0] for k in games)[:100])
                for key, name, icon, games in CATEGORIES])
            select.callback = self.on_category
        p.row(select)
        home = self.page != "home"
        guide = discord.ui.Button(label="Accueil" if home else "Guide du joueur",
                                  emoji=E.partial("pumpkin" if home else "book"),
                                  style=discord.ButtonStyle.secondary)
        guide.callback = self.toggle
        p.row(nav("daily", self.owner_id, "Coffre du jour", "chest", "success"),
              nav("defis", self.owner_id, "Défis", "scroll", "success"),
              nav("profile", self.owner_id, "Profil", "pumpkin_lit", "primary"), guide)
        p.footer(f"{self.footer()} · {random.choice(TIPS)}")
        return p

    def _home(self, p: Panel):
        p.title("Bienvenue dans la Nuit Hantée", icon="pumpkin_lit",
                body="Gagne des **bonbons**, monte de niveau et deviens la terreur du serveur.\n"
                     "Tout se joue avec des boutons, directement ici.")
        p.sep()
        lines = [f"{E(icon)} **{name}** — " + " · ".join(GAME[k][0] for k in games)
                 for key, name, icon, games in CATEGORIES]
        p.text(f"**{len(GAMES)} activités** dans {len(CATEGORIES)} catégories :\n" + "\n".join(lines))
        p.text(f"-# Et aussi : {E.lightning} `/defi` pour un face-à-face en direct · {E.gift} `/echange @membre` pour échanger des cartes · {E.pumpkin_lit} `/puissance4 @membre` · {E.vampire} `/duel` pour défier un membre · {E.skull} `/sort` pour maudire un rival · "
               f"{E.gift} `/donner` pour offrir des bonbons")

    def _category(self, p: Panel, cat):
        key, name, icon, games = cat
        p.title(name, icon=icon, body="Choisis ton jeu dans le menu ci-dessous.")
        p.sep()
        p.text("\n".join(f"{E(GAME[k][1])} **{GAME[k][0]}** `/{COMMAND[k]}` — {GAME[k][2]}" for k in games)
               + "\n-# Chaque jeu s'ouvre dans son propre message : le menu reste là pour les autres.")

    def _guide(self, p: Panel):
        L = config.LIMITS
        p.title("Guide du joueur", icon="book",
                body="Tout ce qu'il faut savoir pour dominer la nuit.")
        p.sep()
        p.text(
            f"### {E.candy} Les bonbons\n"
            f"La monnaie du jeu. Tu en gagnes partout, tu les dépenses à la {E.witch} boutique, "
            f"en {E.gift} boosters ou en {E.vampire} duels. Le classement principal compte tes bonbons **en poche**.\n"
            f"### {E.star} Niveaux & XP\n"
            f"Chaque partie donne de l'XP. Chaque niveau rapporte un bonus de bonbons et un nouveau titre.\n"
            f"### {E.hourglass} Parties par jour\n"
            f"Grand Frisson **{L['quiz']}** émissions · Maison **{L['house']}** · Course **{L['race']}** · Mémoire **{L['memory']}** · "
            f"Chasse **{L['hunt']}** · Pendu **{L['hangman']}** · Rituel **{L['ritual']}** · Ouija **{L['ouija']}** · Bonneteau **{L['shell']}** · Machine **{L['slots']}** · Motus **{L['motus']}** · Plus ou Moins **{L['hilo']}** · Réflexe **{L['reflex']}** · Labyrinthe **{L['maze']}** · Fuite **{L['fuite']}** · Puissance 4 **{L['connect4']}** · Roulette **{L['roulette']}** · Escape **{L['escape']}** · "
            f"Formule **{L['cauldron']}** · Roue toutes les **4 h**. Une nouvelle nuit commence à minuit.\n"
            f"### {E.potion_gold} Effets\n"
            f"Le **Philtre de fortune** double tes gains, le **Philtre de sagesse** double ton XP, "
            f"les **jokers** retirent deux mauvaises réponses, le **bouclier** efface une erreur au Grand Frisson.\n"
            f"### {E.ghost} Apparitions\n"
            f"Dans le salon choisi par les admins, des sacs de bonbons, des quiz éclair et le "
            f"**Roi Citrouille** apparaissent quand le serveur est actif.")

    async def on_pick(self, interaction: discord.Interaction):
        key = interaction.data["values"][0]
        opener = self.bot.openers.get(key)
        if opener:  # each game gets its own message; the menu stays for everyone
            await opener(interaction, edit=False)

    async def on_category(self, interaction: discord.Interaction):
        page = "cat:" + interaction.data["values"][0]
        if interaction.user.id != self.owner_id:
            return await HubView(self.bot, interaction, page=page).start(interaction)
        self.page = page
        await self.refresh(interaction)

    async def toggle(self, interaction: discord.Interaction):
        page = "guide" if self.page == "home" else "home"
        if interaction.user.id != self.owner_id:
            return await HubView(self.bot, interaction, page=page).start(interaction)
        self.page = page
        await self.refresh(interaction)


class Hub(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["hub"] = self.open

    async def open(self, interaction, edit=False, page="home"):
        await HubView(self.bot, interaction, page).start(interaction, edit)

    @app_commands.command(name="jeux", description="🎃 Ouvre la Nuit Hantée : tous les jeux d'Halloween")
    @app_commands.guild_only()
    async def jeux(self, interaction: discord.Interaction):
        await self.open(interaction)

    @app_commands.command(name="aide", description="📖 Le guide du joueur de la Nuit Hantée")
    @app_commands.guild_only()
    async def aide(self, interaction: discord.Interaction):
        await self.open(interaction, page="guide")


async def setup(bot):
    await bot.add_cog(Hub(bot))
