"""/chaudron — mix 2 ingredients, discover the server's 8 secret recipes of the day."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content.games import FAILS, ING, INGREDIENTS, POTION, POTIONS, daily_recipes
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, nav, relative


def apply_potion(store, g, u, key) -> str:
    """Apply a potion's effect, return a short French description."""
    effect = POTION[key]["effect"]
    if effect == "quiz5":
        store.bump(g, u, "quiz_bonus", amount=5)
        return f"{E.potion_blue} **+5 questions** de quiz aujourd'hui !"
    if effect == "luck30":
        until = store.add_effect(g, u, "luck", 1800)
        return f"{E.potion_gold} Tes gains de bonbons sont **doublés** jusqu'à {relative(until)} !"
    if effect == "souls":
        st = store.manor(g, u)
        amount = max(150.0, store.manor_rate(st["units"]) * 60)
        store.manor_add(g, u, amount)
        return f"{E.soul} **+{config.short(amount)} âmes** versées dans ton manoir !"
    if effect == "candy":
        r = grant(store, g, u, 180, 0, "potion")
        return f"{E.candy} **+{config.fmt(r.candies)}** bonbons !"
    if effect == "xp60":
        until = store.add_effect(g, u, "wisdom", 3600)
        return f"{E.potion_green} Ton **XP est doublé** jusqu'à {relative(until)} !"
    if effect == "joker2":
        store.give_item(g, u, "joker", 2)
        return f"{E.joker} **2 jokers 50/50** ajoutés à ton sac !"
    if effect == "shield":
        store.give_item(g, u, "shield", 1)
        return f"{E.shield} **1 bouclier de série** ajouté à ton sac !"
    if effect == "ticket":
        store.give_item(g, u, "ticket", 1)
        return f"{E.wheel} **1 ticket de roue** ajouté à ton sac !"
    return ""


class CauldronView(GameView):
    banner_key = "cauldron"
    owner_hint = "Ouvre ton propre chaudron avec /chaudron."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=600)
        self.state = "idle"
        self.mix: tuple | None = None
        self.result: dict | None = None

    def recipes(self):
        return daily_recipes(self.guild_id, config.today())

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        p = Panel("green").banner(self.banner_key)
        if self.state == "brewing":
            a, b = (ING[k] for k in self.mix)
            p.title("Le chaudron bouillonne…", icon="cauldron",
                    body=f"{E(a['emoji'])} **{a['name']}** + {E(b['emoji'])} **{b['name']}**\n"
                         f"{E.sparkle} *Des bulles étranges remontent à la surface…*")
            p.footer(self.footer())
            return p
        if self.state == "result":
            r = self.result
            if r["potion"]:
                pot = POTION[r["potion"]]
                head = (f"{E.sparkle} **RECETTE SECRÈTE DÉCOUVERTE !**" if r["new"]
                        else f"{E.check} Recette connue, la potion fonctionne !")
                p.title(pot["name"], icon=pot["emoji"], thumb=E.url(pot["emoji"]),
                        body=f"{head}\n{r['text']}" + (f"\n{r['reward'].line()}" if r.get("reward") else ""))
            else:
                p.title("Potion ratée…", icon="skull", body=r["text"])
            p.sep()
        else:
            p.title("Choisis 2 ingrédients…", icon="cauldron",
                    body="Mélange-les dans ton chaudron et découvre ce que ça donne. Certains mélanges sont des "
                         "**recettes secrètes**… et elles **changent chaque nuit à minuit** !")
            p.sep()
        found = self.store.recipes_found(g, u)
        lines = []
        recipes = self.recipes()
        for pair, key in sorted(recipes.items(), key=lambda kv: [x["key"] for x in POTIONS].index(kv[1])):
            pot = POTION[key]
            if key in found:
                a, b = (ING[k] for k in pair)
                lines.append(f"{E(pot['emoji'])} **{pot['name']}** = {E(a['emoji'])} + {E(b['emoji'])} · {pot['desc']}")
            else:
                lines.append(f"{E.question} *Recette secrète…*")
        p.text(f"### {E.book} Ton grimoire du jour\n"
               f"Recettes trouvées : **{len(found)}/{len(POTIONS)}**\n"
               f"-# Avec {config.LIMITS['cauldron']} potions par jour, impossible de tout trouver seul… "
               f"Échange tes recettes avec le serveur !\n" + "\n".join(lines))
        p.sep()
        left = self.store.remaining(g, u, "cauldron")
        p.text(f"{E.hourglass} Potions restantes aujourd'hui : **{left}/{config.LIMITS['cauldron']}**"
               + ("" if left else f" · retour {relative(config.next_midnight_ts())}"))
        select = discord.ui.Select(
            placeholder="Choisis 2 ingrédients à mélanger" if left else "Ton chaudron refroidit jusqu'à minuit…",
            min_values=2, max_values=2, disabled=left <= 0,
            options=[discord.SelectOption(label=i["name"], value=i["key"], emoji=E.partial(i["emoji"]))
                     for i in INGREDIENTS])
        select.callback = self._brew
        p.row(select)
        if left <= 0:
            p.row(nav("quiz", self.owner_id, "Quiz", "crystal"), nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
        p.footer(self.footer("Seul toi peux utiliser ce chaudron"))
        return p

    async def _brew(self, interaction: discord.Interaction):
        async with self.lock:
            if self.state == "brewing":
                return await interaction.response.defer()
            g, u = self.guild_id, self.owner_id
            if not self.store.use_play(g, u, "cauldron"):
                self.state = "idle"
                return await self.refresh(interaction)
            self.mix = tuple(sorted(interaction.data["values"]))
            self.state = "brewing"
            await self.refresh(interaction)
            await asyncio.sleep(1.8)
            key = self.recipes().get(self.mix)
            if key:
                new = self.store.add_recipe(g, u, key)
                text = apply_potion(self.store, g, u, key)
                reward = grant(self.store, g, u, 0, 30 if new else 10, "potion", stats={"potions": 1})
                self.result = dict(potion=key, new=new, text=text, reward=reward)
            else:
                msg, candies = random.choice(FAILS)
                reward = grant(self.store, g, u, candies, 4, "potion")
                text = msg + (f"\n{reward.line()}" if reward.candies or reward.xp else "")
                self.result = dict(potion=None, text=text)
            self.state = "result"
            await self.push()


class Cauldron(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["cauldron"] = self.open

    async def open(self, interaction, edit=False):
        await CauldronView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="chaudron", description="🧪 Mélange 2 ingrédients et trouve les recettes secrètes du jour")
    @app_commands.guild_only()
    async def chaudron(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Cauldron(bot))
