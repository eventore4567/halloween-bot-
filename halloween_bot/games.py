"""Halloween mini-games: ghost hunt, trick-or-treat, quizzes, duels, boss and expedition."""
from __future__ import annotations

import random
import time
import discord
from discord import app_commands
from discord.ext import commands

from .common import card,fail,wait_text,OwnerView
from .content import QUIZZES,RIDDLES,HUNTS


class QuizView(OwnerView):
    def __init__(self,owner_id,guild_id,answers,correct):
        super().__init__(owner_id,timeout=90)
        self.guild_id=guild_id
        self.correct=correct
        self.answers=answers
        self.finished=False
        self.message=None
        for index,answer in enumerate(answers):
            button=discord.ui.Button(label=answer[:80],style=discord.ButtonStyle.secondary)
            async def choose(interaction,i=index):
                if self.finished:
                    return await fail(interaction,"Cette énigme est déjà terminée.")
                self.finished=True
                for component in self.children:
                    component.disabled=True
                if i==self.correct:
                    interaction.client.store.award(self.guild_id,self.owner_id,85,quizzes=1)
                    desc="🎉 **Bonne réponse !**\n\n🍬 **+85 bonbons**."
                else:
                    desc=f"💀 Mauvaise réponse !\n\n🕯️ Réponse : **{self.answers[self.correct]}**."
                await interaction.response.edit_message(embed=card("ÉNIGME TERMINÉE",desc),view=self)
                self.stop()
            button.callback=choose
            self.add_item(button)

    async def on_timeout(self):
        self.finished=True
        for button in self.children:
            button.disabled=True
        if self.message:
            try:
                await self.message.edit(embed=card("ÉNIGME EXPIRÉE","🌫️ L'énigme s'est dissipée."),view=self)
            except discord.HTTPException:
                pass


class DuelView(discord.ui.View):
    def __init__(self,challenger,opponent,guild_id):
        super().__init__(timeout=120)
        self.challenger=challenger
        self.opponent=opponent
        self.guild_id=guild_id
        self.finished=False
        self.message=None

    async def interaction_check(self,interaction):
        if interaction.user.id!=self.opponent:
            await fail(interaction,"Seul le membre défié peut répondre.")
            return False
        return True

    def disable(self):
        for button in self.children:
            button.disabled=True

    @discord.ui.button(label="Accepter",emoji="⚔️",style=discord.ButtonStyle.success)
    async def accept(self,interaction,button):
        if self.finished:
            return await fail(interaction,"Ce duel est terminé.")
        self.finished=True
        winner,loser=random.sample([self.challenger,self.opponent],2)
        interaction.client.store.award(self.guild_id,winner,120,duel_wins=1)
        interaction.client.store.award(self.guild_id,loser,30,duel_losses=1)
        self.disable()
        await interaction.response.edit_message(
            embed=card("DUEL TERMINÉ",
                f"⚔️ <@{self.challenger}> contre <@{self.opponent}>\n\n"
                f"🏆 **<@{winner}> remporte le duel !**\n\n"
                "🍬 Gagnant : **+120**\n🕯️ Participant : **+30**"),
            view=self)
        self.stop()

    @discord.ui.button(label="Refuser",emoji="🕯️",style=discord.ButtonStyle.secondary)
    async def refuse(self,interaction,button):
        if self.finished:
            return await fail(interaction,"Ce duel est terminé.")
        self.finished=True
        self.disable()
        await interaction.response.edit_message(
            embed=card("DUEL REFUSÉ","🕯️ Le membre a décliné le défi."),view=self)
        self.stop()

    async def on_timeout(self):
        if self.finished:
            return
        self.finished=True
        self.disable()
        if self.message:
            try:
                await self.message.edit(embed=card("DUEL EXPIRÉ","🌫️ Personne n'a accepté le duel."),view=self)
            except discord.HTTPException:
                pass


class BossView(discord.ui.View):
    def __init__(self,bot,guild_id):
        super().__init__(timeout=300)
        self.bot=bot
        self.guild_id=guild_id
        self.hp=450
        self.maximum=450
        self.hits={}
        self.last={}
        self.damage={}
        self.finished=False
        self.message=None

    def description(self):
        count=max(0,min(10,round(10*self.hp/self.maximum)))
        bar="🟧"*count+"⬛"*(10-count)
        leaders=sorted(self.damage.items(),key=lambda x:x[1],reverse=True)[:5]
        listing="\n".join(f"⚔️ <@{uid}> · **{amount} dégâts**" for uid,amount in leaders)
        return (
            "╭────── 💀 ──────╮\n"
            "**LE ROI DES CITROUILLES**\n"
            "╰────── 🎃 ──────╯\n\n"
            f"❤️ **{self.hp}/{self.maximum} PV**\n{bar}\n\n"
            "⚔️ **3 attaques par joueur**, une toutes les **10 secondes**.\n"
            "🍬 **150 bonbons** pour chaque participant si le boss tombe.\n\n"
            f"🦇 **Meilleurs combattants**\n{listing or 'Aucun participant.'}"
        )

    @discord.ui.button(label="Attaquer",emoji="⚔️",style=discord.ButtonStyle.danger)
    async def attack(self,interaction,button):
        if self.finished:
            return await fail(interaction,"Ce boss a déjà disparu.")
        uid=interaction.user.id
        if interaction.user.bot:
            return await fail(interaction,"Réservé aux joueurs.")
        now=time.monotonic()
        if self.hits.get(uid,0)>=3:
            return await fail(interaction,"Tu as déjà utilisé tes trois attaques.")
        if now-self.last.get(uid,0)<10:
            return await fail(interaction,"Attends dix secondes entre deux attaques.")
        hit=min(self.hp,random.randint(25,65))
        self.hp-=hit
        self.last[uid]=now
        self.hits[uid]=self.hits.get(uid,0)+1
        self.damage[uid]=self.damage.get(uid,0)+hit
        self.bot.store.award(self.guild_id,uid,boss_damage=hit)
        if self.hp==0:
            self.finished=True
            for member_id in self.damage:
                self.bot.store.award(self.guild_id,member_id,150)
            self.bot.active_bosses.pop(self.guild_id,None)
            for component in self.children:
                component.disabled=True
            await interaction.response.edit_message(
                embed=card("BOSS VAINCU",
                           f"🎃 **Le Roi des Citrouilles est vaincu !**\n\n"
                           f"🏆 **{len(self.damage)} participants récompensés**\n"
                           "🍬 **+150 bonbons** chacun\n\n"+self.description()),
                view=self)
            self.stop()
        else:
            await interaction.response.edit_message(
                embed=card("BOSS HALLOWEEN",self.description()),view=self)

    async def on_timeout(self):
        if self.finished:
            return
        self.finished=True
        self.bot.active_bosses.pop(self.guild_id,None)
        for child in self.children:
            child.disabled=True
        if self.message:
            try:
                await self.message.edit(
                    embed=card("BOSS DISPARU","🌫️ Le Roi des Citrouilles a pris la fuite !"),
                    view=self)
            except discord.HTTPException:
                pass


class ExpeditionView(OwnerView):
    def __init__(self,owner_id,guild_id):
        super().__init__(owner_id,timeout=120)
        self.guild_id=guild_id
        self.finished=False
        self.message=None

    async def explore(self,interaction,door):
        if self.finished:
            return await fail(interaction,"L'expédition est terminée.")
        self.finished=True
        danger={"crypte":0.30,"grenier":0.20,"cave":0.12}[door]
        if random.random()<danger:
            amount=-random.randint(10,40)
            text=f"💀 Un piège se referme !\n\n🍬 Tu perds jusqu'à **{-amount} bonbons**."
        else:
            amount=random.randint(70,160) + (40 if door=="crypte" else 0)
            text=f"✨ **Un coffre ancien !**\n\n🍬 Tu trouves **{amount} bonbons**."
        interaction.client.store.award(self.guild_id,self.owner_id,amount,expeditions=1)
        for child in self.children:
            child.disabled=True
        await interaction.response.edit_message(
            embed=card("MAISON HANTÉE",text),view=self)
        self.stop()

    @discord.ui.button(label="La crypte",emoji="💀",style=discord.ButtonStyle.danger)
    async def crypt(self,interaction,button):
        await self.explore(interaction,"crypte")

    @discord.ui.button(label="Le grenier",emoji="🦇",style=discord.ButtonStyle.primary)
    async def attic(self,interaction,button):
        await self.explore(interaction,"grenier")

    @discord.ui.button(label="La cave",emoji="🕯️",style=discord.ButtonStyle.secondary)
    async def cellar(self,interaction,button):
        await self.explore(interaction,"cave")

    async def on_timeout(self):
        self.finished=True
        for button in self.children:
            button.disabled=True
        if self.message:
            try:
                await self.message.edit(
                    embed=card("EXPLORATION EXPIRÉE","🌫️ Les portes se sont refermées."),
                    view=self)
            except discord.HTTPException:
                pass


class Games(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    @app_commands.command(name="trickortreat",description="👻 Un bonbon ou un sort ?")
    @app_commands.guild_only()
    async def trickortreat(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"trick",900)
        if wait:
            return await fail(interaction,wait_text(wait))
        result=random.choices(["treat","jackpot","trick","nothing"],[58,9,23,10])[0]
        if result=="treat":
            amount=random.randint(45,135)
            message=f"🍬 Une sorcière t'offre **{amount} bonbons** !"
        elif result=="jackpot":
            amount=random.randint(200,420)
            message=f"✨ **JACKPOT !** Tu gagnes **{amount} bonbons** !"
        elif result=="trick":
            amount=-random.randint(15,65)
            message=f"💀 Un fantôme vole jusqu'à **{-amount} bonbons** !"
        else:
            amount=0
            message="🌫️ Ton panier reste vide cette fois..."
        p=self.bot.store.award(g,u,amount)
        await interaction.response.send_message(embed=card(
            "UN BONBON OU UN SORT ?",message+
            f"\n\n🎃 Solde : **{p['candies']:,} 🍬**"))

    @app_commands.command(name="ghosthunt",description="🦇 Partir à la chasse aux fantômes")
    @app_commands.guild_only()
    async def ghosthunt(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"hunt",300)
        if wait:
            return await fail(interaction,wait_text(wait))
        if random.random()<0.28:
            message="🌫️ Tu traverses le cimetière... le fantôme s'enfuit !\n\n💀 Aucune récompense."
        else:
            name,low,high=random.choices(HUNTS,weights=[45,30,20,5])[0]
            amount=random.randint(low,high)
            self.bot.store.award(g,u,amount,ghosts=1)
            message=f"🌙 **Un spectre surgit du brouillard !**\n\n{name} capturé.\n\n👻 +1 fantôme\n🍬 **+{amount} bonbons**"
        await interaction.response.send_message(embed=card("CHASSE AUX FANTÔMES",message))

    @app_commands.command(name="pumpkin",description="🎃 Ouvrir une citrouille mystérieuse")
    @app_commands.guild_only()
    async def pumpkin(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"pumpkin",600)
        if wait:
            return await fail(interaction,wait_text(wait))
        kind=random.choices(["simple","rare","legendary","empty"],[56,31,5,8])[0]
        amount={
            "simple":random.randint(30,90),
            "rare":random.randint(100,220),
            "legendary":random.randint(350,650),
            "empty":0
        }[kind]
        p=self.bot.store.award(g,u,amount,pumpkins=1)
        descriptions={
            "simple":"🎃 Une citrouille pleine de sucreries !",
            "rare":"🦇 **CITROUILLE RARE !**",
            "legendary":"✨ **CITROUILLE LÉGENDAIRE !**",
            "empty":"🕸️ Cette citrouille était vide..."
        }
        await interaction.response.send_message(embed=card(
            "CITROUILLE MYSTÉRIEUSE",
            f"{descriptions[kind]}\n\n🍬 **+{amount} bonbons**\n"
            f"🪙 Solde : **{p['candies']:,}**"))

    @app_commands.command(name="quiz",description="🧩 Répondre aux questions d'Halloween")
    @app_commands.guild_only()
    async def quiz(self,interaction:discord.Interaction,
                   mode:Literal["questions","enigmes"]="questions"):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"quiz",240)
        if wait:
            return await fail(interaction,wait_text(wait))
        question,answers,correct=random.choice(RIDDLES if mode=="enigmes" else QUIZZES)
        view=QuizView(u,g,answers,correct)
        await interaction.response.send_message(
            embed=card("ÉNIGME DE LA CRYPTE",
                       f"🧩 **{question}**\n\n🕯️ Tu as 90 secondes."),
            view=view,ephemeral=True)
        view.message=await interaction.original_response()

    @app_commands.command(name="duel",description="⚔️ Défier un joueur à un duel")
    @app_commands.guild_only()
    async def duel(self,interaction:discord.Interaction,adversaire:discord.Member):
        if adversaire.bot or adversaire.id==interaction.user.id:
            return await fail(interaction,"Choisis un autre joueur humain.")
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"duel",300)
        if wait:
            return await fail(interaction,wait_text(wait))
        view=DuelView(u,adversaire.id,g)
        await interaction.response.send_message(
            embed=card("DÉFI HALLOWEEN",
                       f"⚔️ {interaction.user.mention} défie {adversaire.mention} !\n\n"
                       "🏆 Victoire : **+120 🍬**\n"
                       "🕯️ Participation : **+30 🍬**\n\n"
                       "🎃 Duel amical sans mise."),
            view=view,allowed_mentions=discord.AllowedMentions(users=[adversaire]))
        view.message=await interaction.original_response()

    @app_commands.command(name="boss",description="💀 Invoquer un boss communautaire")
    @app_commands.guild_only()
    async def boss(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        if g in self.bot.active_bosses:
            return await fail(interaction,"Un boss est déjà présent !")
        wait=self.bot.store.cooldown(g,0,"boss_global",1200)
        if wait:
            return await fail(interaction,wait_text(wait))
        view=BossView(self.bot,g)
        self.bot.active_bosses[g]=view
        await interaction.response.send_message(
            embed=card("BOSS HALLOWEEN",view.description()),view=view)
        view.message=await interaction.original_response()

    @app_commands.command(name="expedition",description="🏚️ Explorer une maison hantée")
    @app_commands.guild_only()
    async def expedition(self,interaction:discord.Interaction):
        g,u=interaction.guild.id,interaction.user.id
        wait=self.bot.store.cooldown(g,u,"expedition",600)
        if wait:
            return await fail(interaction,wait_text(wait))
        view=ExpeditionView(u,g)
        await interaction.response.send_message(
            embed=card("LA MAISON HANTÉE",
                "🌫️ Trois portes apparaissent devant toi...\n\n"
                "💀 **La crypte** — Récompenses élevées, danger élevé\n"
                "🦇 **Le grenier** — Danger moyen\n"
                "🕯️ **La cave** — Danger faible\n\n"
                "🏚️ Choisis ton chemin. Tu as 2 minutes."),
            view=view,ephemeral=True)
        view.message=await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Games(bot))
