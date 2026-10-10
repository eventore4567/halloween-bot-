"""Bonbons, shop, collections, achievements and leaderboards."""
from __future__ import annotations

import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ..common import card, fail, format_rank, OwnerView, wait_text
from ..content import ITEMS, ACHIEVEMENTS


GUIDE = (
    "🍬 /daily — Panier quotidien\n"
    "👻 /trickortreat — Un bonbon ou un sort\n"
    "🦇 /ghosthunt — Chasser des fantômes\n"
    "🎃 /pumpkin — Citrouille mystérieuse\n"
    "🧩 /quiz — Questions et énigmes\n"
    "⚔️ /duel — Défier un membre\n"
    "💀 /boss — Combat communautaire\n"
    "🌾 /farm — Cultiver des citrouilles\n"
    "🏚️ /expedition — Explorer une maison hantée\n"
    "🏆 /leaderboard — Classement du serveur\n"
    "🛒 /shop — Boutique Halloween\n"
    "🎒 /inventory — Collection personnelle\n"
    "🏅 /achievements — Succès à débloquer\n"
    "🎁 /give — Donner des bonbons\n"
    "⚙️ /setup — Choisir le salon d'événements (admins)\n\n"
    "🕸️ Tous les jeux sont disponibles sans réglage compliqué."
)


def profile_text(bot, guild_id, member):
    data=bot.store.profile(guild_id, member.id)
    rank=bot.store.position(guild_id, member.id)
    return (
        f"🧙 **Joueur :** {member.mention}\n\n"
        f"🍬 Bonbons : **{data['candies']:,}**\n"
        f"👻 Fantômes : **{data['ghosts']}**\n"
        f"🎃 Citrouilles : **{data['pumpkins']}**\n"
        f"🌾 Récoltes : **{data['harvests']}**\n"
        f"🏚️ Expéditions : **{data['expeditions']}**\n"
        f"⚔️ Duels gagnés : **{data['duel_wins']}**\n"
        f"🧩 Quiz réussis : **{data['quizzes']}**\n"
        f"🏆 Rang bonbons : **#{rank}**\n"
        f"🕯️ Total obtenu : **{data['earned']:,} 🍬**"
    )


def shop_card():
    lines=[f"**{name}** · **{price:,} 🍬**\n└ {description}"
           for name,price,description in ITEMS.values()]
    return card("LA BOUTIQUE HANTÉE",
                "🕸️ **Objets de collection du royaume**\n\n"
                + "\n\n".join(lines)
                + "\n\n🎃 Choisis un article avec le menu.",purple=True)


class ShopSelect(discord.ui.Select):
    def __init__(self):
        options=[
            discord.SelectOption(label=name,value=key,
                                 description=f"{price} bonbons",emoji=name.split()[0])
            for key,(name,price,_) in ITEMS.items()
        ]
        super().__init__(placeholder="🛒 Choisir un objet", options=options)

    async def callback(self,interaction):
        key=self.values[0]
        name,price,description=ITEMS[key]
        if not interaction.client.store.buy(interaction.guild.id,interaction.user.id,key,price):
            return await fail(interaction,"Pas assez de bonbons. Joue pour en récolter !")
        remaining=interaction.client.store.profile(interaction.guild.id,interaction.user.id)["candies"]
        await interaction.response.send_message(
            embed=card("ACHAT EFFECTUÉ",
                       f"✅ **{name}** ajouté à ton inventaire !\n\n"
                       f"🍬 Prix : **{price}**\n"
                       f"🎒 Solde : **{remaining:,}**\n\n{description}"),
            ephemeral=True)


class ShopView(OwnerView):
    def __init__(self,owner_id):
        super().__init__(owner_id)
        self.add_item(ShopSelect())


class HubView(OwnerView):
    @discord.ui.button(label="Mon profil",emoji="🎃",style=discord.ButtonStyle.primary,row=0)
    async def my_profile(self,interaction,button):
        await interaction.response.send_message(
            embed=card("MON PROFIL",profile_text(interaction.client,interaction.guild.id,interaction.user)),
            ephemeral=True)

    @discord.ui.button(label="Classement",emoji="🏆",style=discord.ButtonStyle.secondary,row=0)
    async def top(self,interaction,button):
        rows=interaction.client.store.ranking(interaction.guild.id)
        await interaction.response.send_message(
            embed=card("TOP 10 DES BONBONS",format_rank(interaction.guild,rows)),
            ephemeral=True)

    @discord.ui.button(label="Boutique",emoji="🛒",style=discord.ButtonStyle.success,row=0)
    async def store(self,interaction,button):
        await interaction.response.send_message(
            embed=shop_card(),view=ShopView(interaction.user.id),ephemeral=True)

    @discord.ui.button(label="Guide",emoji="🦇",style=discord.ButtonStyle.secondary,row=1)
    async def guide(self,interaction,button):
        await interaction.response.send_message(
            embed=card("GUIDE HALLOWEEN",GUIDE),ephemeral=True)

    @discord.ui.button(label="Ma ferme",emoji="🌾",style=discord.ButtonStyle.secondary,row=1)
    async def farm(self,interaction,button):
        cog=interaction.client.get_cog("Farming")
        await cog.send_farm(interaction)


class Economy(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    @app_commands.command(name="halloween",description="🎃 Ouvre le panneau Halloween")
    @app_commands.guild_only()
    async def halloween(self,interaction:discord.Interaction):
        data=self.bot.store.profile(interaction.guild.id,interaction.user.id)
        body=(
            "╭────── 🕸️ ──────╮\n"
            "**LE ROYAUME D'HALLOWEEN**\n"
            "╰────── 🎃 ──────╯\n\n"
            "👻 Explore, récolte, chasse et collectionne.\n\n"
            f"🍬 **Ton panier : {data['candies']:,} bonbons**\n\n"
            "🎮 **Jeux** — /trickortreat · /ghosthunt · /quiz · /duel · /boss\n"
            "🌾 **Farming** — /farm · /pumpkin · /expedition\n"
            "🏆 **Progression** — /leaderboard · /achievements\n\n"
            "🦇 Utilise les boutons ci-dessous pour commencer."
        )
        await interaction.response.send_message(
            embed=card("HALLOWEEN BOT",body),view=HubView(interaction.user.id))

    @app_commands.command(name="daily",description="🍬 Ouvre ton panier quotidien")
    @app_commands.guild_only()
    async def daily(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"daily",86400)
        if wait:
            return await fail(interaction,wait_text(wait))
        amount=random.randint(120,260)
        profile=self.bot.store.award(g,u,amount)
        await interaction.response.send_message(embed=card(
            "BONBONS QUOTIDIENS",
            f"🎃 Ton panier vient d'être rempli !\n\n"
            f"🍬 **+{amount} bonbons**\n"
            f"🪙 Nouveau solde : **{profile['candies']:,}**\n\n"
            "🕯️ Reviens demain !"))

    @app_commands.command(name="profile",description="🎃 Voir les statistiques d'un joueur")
    @app_commands.guild_only()
    async def profile(self,interaction:discord.Interaction,membre:discord.Member|None=None):
        target=membre or interaction.user
        await interaction.response.send_message(
            embed=card("PROFIL HALLOWEEN",profile_text(self.bot,interaction.guild.id,target)))

    @app_commands.command(name="leaderboard",description="🏆 Classement des meilleurs joueurs")
    @app_commands.guild_only()
    async def leaderboard(self,interaction:discord.Interaction,
                          categorie:Literal["bonbons","fantomes","duels","total","ferme","exploration"]="bonbons"):
        choices={
            "bonbons":("candies","🍬"),"fantomes":("ghosts","👻"),
            "duels":("duel_wins","⚔️"),"total":("earned","🍬"),
            "ferme":("harvests","🌾"),"exploration":("expeditions","🏚️")
        }
        field,emoji=choices[categorie]
        rows=self.bot.store.ranking(interaction.guild.id,field)
        await interaction.response.send_message(
            embed=card("CLASSEMENT · "+categorie.upper(),
                       format_rank(interaction.guild,rows,emoji),purple=True))

    @app_commands.command(name="shop",description="🛒 Acheter des objets Halloween")
    @app_commands.guild_only()
    async def shop(self,interaction:discord.Interaction):
        await interaction.response.send_message(
            embed=shop_card(),view=ShopView(interaction.user.id),ephemeral=True)

    @app_commands.command(name="inventory",description="🎒 Consulter tes objets de collection")
    @app_commands.guild_only()
    async def inventory(self,interaction:discord.Interaction):
        inv=self.bot.store.inventory(interaction.guild.id,interaction.user.id)
        lines=[f"{ITEMS[x['item']][0]} × **{x['quantity']}**"
               for x in inv if x["item"] in ITEMS]
        await interaction.response.send_message(
            embed=card("MON INVENTAIRE","\n".join(lines) if lines else
                       "🕸️ Ton sac est vide. Découvre /shop !"),ephemeral=True)

    @app_commands.command(name="give",description="🎁 Offrir des bonbons à un membre")
    @app_commands.guild_only()
    async def give(self,interaction:discord.Interaction,membre:discord.Member,
                   bonbons:app_commands.Range[int,1,10000]):
        if membre.bot or membre.id==interaction.user.id:
            return await fail(interaction,"Choisis un autre joueur humain.")
        if not self.bot.store.gift(interaction.guild.id,interaction.user.id,membre.id,bonbons):
            return await fail(interaction,"Solde insuffisant.")
        await interaction.response.send_message(embed=card(
            "CADEAU HALLOWEEN",
            f"🎁 {interaction.user.mention} offre **{bonbons:,} 🍬** à {membre.mention} !"))

    @app_commands.command(name="achievements",description="🏅 Débloquer les succès Halloween")
    @app_commands.guild_only()
    async def achievements(self,interaction:discord.Interaction):
        p=self.bot.store.profile(interaction.guild.id,interaction.user.id)
        unlocked=sum(check(p) for _,check in ACHIEVEMENTS)
        lines=[f"{'✅' if check(p) else '🔒'} {name}"
               for name,check in ACHIEVEMENTS]
        await interaction.response.send_message(embed=card(
            "SUCCÈS HALLOWEEN",
            f"🏅 **{unlocked}/{len(ACHIEVEMENTS)} succès**\n\n"+"\n".join(lines)),
            ephemeral=True)

    @app_commands.command(name="guide",description="🦇 Voir toutes les commandes du bot")
    @app_commands.guild_only()
    async def guide(self,interaction:discord.Interaction):
        await interaction.response.send_message(
            embed=card("GUIDE",GUIDE),ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
