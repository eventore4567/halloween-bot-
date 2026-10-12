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
    ("quiz", "Quiz maudit", "crystal", f"{quiz_bank.TOTAL} questions, 5 niveaux, combos et jokers"),
    ("manor", "Le Manoir", "soul", "Recrute des monstres qui récoltent des âmes pour toi"),
    ("cauldron", "L'Alchimiste", "cauldron", "Trouve les 8 recettes secrètes du jour"),
    ("wheel", "Roue du destin", "wheel", "Un tour gratuit toutes les 4 heures"),
    ("cards", "Cartes maudites", "gift", "Collectionne les 24 monstres"),
    ("memory", "Mémoire d'outre-tombe", "eye", "Retrouve les 8 paires"),
    ("hunt", "Chasse aux fantômes", "ghost", "Creuse les tombes… évite la Faucheuse"),
    ("hangman", "Le Pendu", "skull", "Sauve le squelette lettre par lettre"),
    ("daily", "Coffre du jour", "chest", "Ta récompense quotidienne + série"),
    ("shop", "La Boutique", "witch", "Jokers, potions, titres et thèmes"),
    ("top", "Le Panthéon", "trophy", "Les classements du serveur"),
    ("profile", "Mon profil", "pumpkin_lit", "Ta carte de chasseur et tes quotas"),
]

TIPS = [
    "Les recettes du chaudron changent chaque nuit à minuit : partage-les avec le serveur !",
    "Une bonne série au quiz multiplie tes gains jusqu'à ×2.",
    "Le Philtre de fortune double TOUS tes gains de bonbons pendant 30 minutes.",
    "Tes monstres du manoir travaillent même quand tu dors (jusqu'à 12 h).",
    "Réponds vite au quiz : un bonus de rapidité t'attend.",
    "Ne rate pas un jour de coffre : la série monte jusqu'à 7 jours.",
    "Défie un ami avec /duel et mise tes bonbons !",
    "Garde l'œil sur le salon des apparitions : le premier qui clique gagne.",
]


class HubView(GameView):
    banner_key = "hub"

    def __init__(self, bot, interaction, page="home"):
        super().__init__(bot, interaction, timeout=600)
        self.page = page

    async def interaction_check(self, interaction):
        return True  # anyone can use the hub; others get their own panel

    def build(self) -> Panel:
        p = Panel("orange").banner(self.banner_key)
        if self.page == "guide":
            self._guide(p)
        else:
            self._home(p)
        p.sep()
        select = discord.ui.Select(placeholder="Choisis un jeu…", options=[
            discord.SelectOption(label=name, value=key, emoji=E.partial(icon), description=desc[:100])
            for key, name, icon, desc in GAMES])
        select.callback = self.on_pick
        p.row(select)
        guide = discord.ui.Button(label="Accueil" if self.page == "guide" else "Guide du joueur",
                                  emoji=E.partial("pumpkin" if self.page == "guide" else "book"),
                                  style=discord.ButtonStyle.secondary)
        guide.callback = self.toggle
        p.row(nav("daily", self.owner_id, "Coffre du jour", "chest", "success"),
              nav("profile", self.owner_id, "Profil", "pumpkin_lit", "primary"), guide)
        p.footer(f"{self.footer()} · {random.choice(TIPS)}")
        return p

    def _home(self, p: Panel):
        p.title("Bienvenue dans la Nuit Hantée", icon="pumpkin_lit",
                body="Gagne des **bonbons**, monte de niveau et deviens la terreur du serveur.\n"
                     "Tout se joue avec des boutons, directement ici.")
        p.sep()
        lines = [f"{E(icon)} **{name}** — {desc}" for key, name, icon, desc in GAMES[:9]]
        p.text("\n".join(lines))
        p.text(f"-# Et aussi : {E.vampire} `/duel` pour défier un membre · {E.gift} `/donner` pour offrir des bonbons")

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
            f"Quiz **{L['quiz']}** · Mémoire **{L['memory']}** · Chasse **{L['hunt']}** · Pendu **{L['hangman']}** · "
            f"Potions **{L['cauldron']}** · Roue toutes les **4 h**. Tout revient à zéro à minuit.\n"
            f"### {E.potion_gold} Effets\n"
            f"Le **Philtre de fortune** double tes gains, le **Philtre de sagesse** double ton XP, "
            f"les **jokers** retirent deux mauvaises réponses, le **bouclier** protège ta série.\n"
            f"### {E.ghost} Apparitions\n"
            f"Dans le salon choisi par les admins, des sacs de bonbons, des quiz éclair et le "
            f"**Roi Citrouille** apparaissent quand le serveur est actif.")

    async def on_pick(self, interaction: discord.Interaction):
        key = interaction.data["values"][0]
        opener = self.bot.openers.get(key)
        if opener:
            if interaction.user.id == self.owner_id:
                self.finish()
            await opener(interaction, edit=interaction.user.id == self.owner_id)

    async def toggle(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            view = HubView(self.bot, interaction, page="guide")
            return await view.start(interaction)
        self.page = "home" if self.page == "guide" else "guide"
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
