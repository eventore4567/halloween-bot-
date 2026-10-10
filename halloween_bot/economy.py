"""Halloween hub, economy, leaderboard, collectibles and achievements."""
from __future__ import annotations

import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .common import card, fail, format_rank, OwnerView, themed_view, wait_text
from .content import ITEMS, ACHIEVEMENTS


def profile_card(bot, guild, member):
    data = bot.store.profile(guild.id, member.id)
    rank = bot.store.position(guild.id, member.id)
    panel = card(
        "Ton profil de chasseur",
        f"**{member.mention}**  ·  Ton aventure dans le royaume hanté.",
        theme="night",
        sections=[
            ("🍬  BONBONS", f"**{data['candies']:,}**", True),
            ("🏆  CLASSEMENT", f"**#{rank or '—'}**", True),
            ("👻  FANTÔMES", f"**{data['ghosts']}**", True),
            ("🦇  AVENTURES",
             f"⚔️ Victoires : **{data['duel_wins']}**\n"
             f"🧩 Énigmes : **{data['quizzes']}**\n"
             f"🏚️ Expéditions : **{data['expeditions']}**", False),
            ("🌾  FARMING",
             f"🎃 Citrouilles ouvertes : **{data['pumpkins']}**\n"
             f"🌱 Récoltes : **{data['harvests']}**", False),
            ("✨  PROGRESSION",
             f"Total gagné depuis le début : **{data['earned']:,} 🍬**", False),
        ],
        thumbnail=False,
    )
    panel.set_thumbnail(url=member.display_avatar.url)
    return panel


def shop_card():
    sections = []
    pairs = list(ITEMS.values())
    for index in range(0, len(pairs), 2):
        left, right = pairs[index:index + 2]
        lines = [
            f"**{name}**\n"
            f"└ {description}\n"
            f"　**{price:,} bonbons**"
            for name, price, description in (left, right)
        ]
        sections.append(("🛒  OBJETS À COLLECTIONNER", "\n\n".join(lines), False))
    return card(
        "La boutique hantée",
        "🕯️ De mystérieux objets sont en vente pour tes bonbons.",
        theme="night",
        sections=sections,
        note="Choisis un objet dans le menu ci-dessous. "
             "Les achats sont conservés dans ton inventaire.",
    )


class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=name.split(" ", 1)[1],
                value=key,
                description=f"{price:,} bonbons • {detail[:65]}",
                emoji=name.split(" ", 1)[0],
            )
            for key, (name, price, detail) in ITEMS.items()
        ]
        super().__init__(
            placeholder="Choisir un objet de la boutique",
            options=options,
        )

    async def callback(self, interaction):
        key = self.values[0]
        name, price, detail = ITEMS[key]
        store = interaction.client.store
        if not store.buy(interaction.guild.id, interaction.user.id, key, price):
            return await fail(interaction, "Pas assez de bonbons. Continue tes aventures !")
        remaining = store.profile(interaction.guild.id, interaction.user.id)["candies"]
        await interaction.response.send_message(
            embed=card(
                "Achat confirmé",
                f"**{name}**\n{detail}",
                theme="success",
                sections=[
                    ("🍬  PRIX", f"**{price:,}**", True),
                    ("🎒  SOLDE", f"**{remaining:,}**", True),
                ],
                note="Cet objet est maintenant dans /inventory.",
            ),
            ephemeral=True,
        )


class ShopView(OwnerView):
    def __init__(self, owner_id):
        super().__init__(owner_id)
        self.add_item(ShopSelect())
        themed_view(self)


class HubView(OwnerView):
    @discord.ui.button(label="Mon profil", emoji="🎃", style=discord.ButtonStyle.primary, row=0)
    async def my_profile(self, interaction, button):
        await interaction.response.send_message(
            embed=profile_card(interaction.client, interaction.guild, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(label="Classement", emoji="🏆", style=discord.ButtonStyle.secondary, row=0)
    async def top(self, interaction, button):
        from .competition import top_card
        await interaction.response.send_message(
            embed=top_card(interaction.client, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(label="Boutique", emoji="🛒", style=discord.ButtonStyle.success, row=0)
    async def shop(self, interaction, button):
        await interaction.response.send_message(
            embed=shop_card(), view=ShopView(interaction.user.id), ephemeral=True
        )

    @discord.ui.button(label="Les jeux", emoji="🦇", style=discord.ButtonStyle.secondary, row=1)
    async def guide(self, interaction, button):
        await interaction.response.send_message(embed=guide_card(), ephemeral=True)

    @discord.ui.button(label="Ma ferme", emoji="🌾", style=discord.ButtonStyle.secondary, row=1)
    async def farm(self, interaction, button):
        cog = interaction.client.get_cog("Farming")
        await cog.send_farm(interaction)

    @discord.ui.button(label="Compétition", emoji="💎", style=discord.ButtonStyle.success, row=1)
    async def tournament(self, interaction, button):
        from .competition import competition_card, CompetitionView
        await interaction.response.send_message(
            embed=competition_card(interaction.client, interaction.guild, interaction.user),
            view=CompetitionView(),
            ephemeral=True,
        )


def guide_card():
    return card(
        "Le grimoire du royaume",
        "📜 Tout ce qu'il faut savoir pour survivre à la nuit.",
        theme="night",
        sections=[
            ("🍬  GAGNER DES BONBONS",
             "/daily — panier quotidien\n"
             "/trickortreat — un bonbon ou un sort\n"
             "/pumpkin — citrouille surprise", False),
            ("👻  JOUER ET SE DÉFIER",
             "/ghosthunt — chasse aux fantômes\n"
             "/quiz — énigmes et questions\n"
             "/duel — duel entre joueurs\n"
             "/boss — boss communautaire\n"
             "/expedition — maison hantée", False),
            ("🌾  CULTIVER ET COLLECTIONNER",
             "/farm — plantation et récoltes\n"
             "/shop — boutique\n"
             "/inventory — tes objets", False),
            ("🏆  HALLOWEEN CUP • COMPÉTITION",
             "/competition — arène, inscription et règlement\n"
             "/challenge — trois épreuves de compétence quotidiennes\n"
             "/competition_top — classement de la saison\n"
             "/competition_rank — rang et division", False),
            ("🎒  COLLECTION ET PROGRESSION",
             "/profile — statistiques\n"
             "/leaderboard — classements du serveur\n"
             "/achievements — succès\n"
             "/give — offrir des bonbons", False),
        ],
        note="Un administrateur utilise /setup une seule fois "
             "pour choisir le salon des événements automatiques.",
    )


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="halloween", description="🎃 Ouvre le royaume Halloween")
    @app_commands.guild_only()
    async def halloween(self, interaction: discord.Interaction):
        g, u = interaction.guild.id, interaction.user.id
        p = self.bot.store.profile(g, u)
        rank = self.bot.store.position(g, u)
        contest_rank = self.bot.competition.position(g, u)
        contest_name = (
            f"#{contest_rank['place']} • {contest_rank['score']:,} points"
            if contest_rank else "Pas encore inscrit"
        )
        main = card(
            "Bienvenue dans le royaume hanté",
            "La nuit est tombée. Les fantômes rôdent et les citrouilles "
            "n'attendent que toi.\n\n**Ton aventure commence ici.**",
            theme="pumpkin",
            sections=[
                ("🍬  TON PANIER", f"**{p['candies']:,}**", True),
                ("🍬  RANG BONBONS", f"**#{rank or '—'}**", True),
                ("👻  CAPTURES", f"**{p['ghosts']}**", True),
                ("🦇  JOUER",
                 "Trick or Treat · Chasse · Énigmes · Duels · Boss", False),
                ("🌾  EXPLORER",
                 "Potager hanté · Maison abandonnée · Collection", False),
                ("🏆  HALLOWEEN CUP • TA SAISON",
                 f"**{contest_name}**\n"
                 "Tes points de compétition ne dépendent pas des bonbons.", False),
            ],
            note="Choisis une rubrique avec les boutons ci-dessous.",
            thumbnail=True,
        )
        await interaction.response.send_message(embed=main, view=HubView(u))

    @app_commands.command(name="daily", description="🍬 Ouvre ton panier quotidien")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction):
        g, u = interaction.guild.id, interaction.user.id
        remaining = self.bot.store.cooldown(g, u, "daily", 86400)
        if remaining:
            return await fail(interaction, wait_text(remaining))
        amount = random.randint(120, 260)
        p = self.bot.store.award(g, u, amount)
        await interaction.response.send_message(embed=card(
            "Panier quotidien ouvert",
            "🎃 Un panier plein de sucreries t'attendait devant la porte.",
            theme="success",
            sections=[
                ("🍬  RÉCOMPENSE", f"**+{amount}**", True),
                ("🎒  NOUVEAU SOLDE", f"**{p['candies']:,}**", True),
            ],
            note="Tu pourras récupérer un nouveau panier dans 24 heures.",
        ))

    @app_commands.command(name="profile", description="🎃 Consulter un profil Halloween")
    @app_commands.guild_only()
    async def profile(self, interaction: discord.Interaction,
                      membre: discord.Member | None = None):
        await interaction.response.send_message(
            embed=profile_card(self.bot, interaction.guild, membre or interaction.user)
        )

    @app_commands.command(name="leaderboard", description="🏆 Classements du serveur")
    @app_commands.guild_only()
    async def leaderboard(
        self, interaction: discord.Interaction,
        categorie: Literal["competition", "bonbons", "fantomes", "duels", "total", "ferme", "exploration"] = "competition",
    ):
        if categorie == "competition":
            from .competition import top_card
            return await interaction.response.send_message(
                embed=top_card(self.bot, interaction.guild)
            )
        types = {
            "bonbons": ("candies", "🍬", "Bonbons"),
            "fantomes": ("ghosts", "👻", "Fantômes capturés"),
            "duels": ("duel_wins", "⚔️", "Duels gagnés"),
            "total": ("earned", "✨", "Bonbons obtenus"),
            "ferme": ("harvests", "🌾", "Récoltes"),
            "exploration": ("expeditions", "🏚️", "Expéditions"),
        }
        stat, icon, title = types[categorie]
        rows = self.bot.store.ranking(interaction.guild.id, stat)
        await interaction.response.send_message(embed=card(
            f"Classement • {title}",
            f"{icon} **Les 10 meilleurs joueurs du serveur**",
            theme="gold",
            sections=[("🏆  TOP 10", format_rank(interaction.guild, rows, icon), False)],
            note="Chaque serveur possède son propre classement.",
        ))

    @app_commands.command(name="shop", description="🛒 Boutique des objets Halloween")
    @app_commands.guild_only()
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=shop_card(), view=ShopView(interaction.user.id), ephemeral=True
        )

    @app_commands.command(name="inventory", description="🎒 Consulter tes objets de collection")
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction):
        stored = self.bot.store.inventory(interaction.guild.id, interaction.user.id)
        lines = [
            f"{ITEMS[x['item']][0]}  × **{x['quantity']}**"
            for x in stored if x["item"] in ITEMS
        ]
        panel = card(
            "Ton inventaire",
            "🎒 Voici les trésors que tu as trouvés ou achetés.",
            theme="night",
            sections=[
                ("🗝️  MES OBJETS",
                 "\n\n".join(lines) if lines else
                 "🕸️ Rien pour le moment. La boutique t'attend avec /shop.", False)
            ],
        )
        await interaction.response.send_message(embed=panel, ephemeral=True)

    @app_commands.command(name="give", description="🎁 Offrir des bonbons")
    @app_commands.guild_only()
    async def give(
        self, interaction: discord.Interaction, membre: discord.Member,
        bonbons: app_commands.Range[int, 1, 10000],
    ):
        if membre.bot or membre.id == interaction.user.id:
            return await fail(interaction, "Choisis un autre joueur humain.")
        if not self.bot.store.gift(interaction.guild.id, interaction.user.id, membre.id, bonbons):
            return await fail(interaction, "Tu n'as pas assez de bonbons.")
        await interaction.response.send_message(embed=card(
            "Un cadeau dans la nuit",
            f"🎁 {interaction.user.mention} offre des bonbons à {membre.mention} !",
            theme="success",
            sections=[("🍬  CADEAU", f"**{bonbons:,} bonbons**", False)],
        ))

    @app_commands.command(name="achievements", description="🏅 Tes succès Halloween")
    @app_commands.guild_only()
    async def achievements(self, interaction: discord.Interaction):
        p = self.bot.store.profile(interaction.guild.id, interaction.user.id)
        unlocked = [name for name, check in ACHIEVEMENTS if check(p)]
        locked = [name for name, check in ACHIEVEMENTS if not check(p)]
        await interaction.response.send_message(embed=card(
            "Tes succès",
            f"🏆 **{len(unlocked)} sur {len(ACHIEVEMENTS)} réussis**",
            theme="gold",
            sections=[
                ("✅  DÉBLOQUÉS",
                 "\n".join(unlocked) if unlocked else "Aucun succès pour le moment.", False),
                ("🔒  ENCORE À DÉCOUVRIR",
                 "\n".join(locked) if locked else "Tous les succès sont débloqués !", False),
            ],
        ), ephemeral=True)

    @app_commands.command(name="guide", description="🦇 Guide des jeux Halloween")
    @app_commands.guild_only()
    async def guide(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=guide_card(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
