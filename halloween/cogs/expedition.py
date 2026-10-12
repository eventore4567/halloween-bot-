"""/expedition — send up to 3 of your monster cards on a timed mission."""
from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from ..content.games import CARD, RARITIES
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

DESTINATIONS = [
    dict(key="forest", name="Forêt des Pendus", emoji="spider", minutes=30, chance=0.80, reward=(70, 130), xp=15,
         booster=0.0, story="Ils s'enfoncent entre les arbres tordus…"),
    dict(key="swamp", name="Marais des Feux follets", emoji="soul", minutes=120, chance=0.65, reward=(220, 380), xp=35,
         booster=0.12, story="Les feux follets dansent au-dessus de l'eau noire…"),
    dict(key="castle", name="Château de Dracula", emoji="vampire", minutes=360, chance=0.50, reward=(600, 1000), xp=70,
         booster=0.25, story="Le pont-levis grince. Personne n'en est jamais revenu… paraît-il."),
]
DEST = {d["key"]: d for d in DESTINATIONS}
RARITY_BONUS = {"C": (0.04, 0.05), "R": (0.08, 0.10), "E": (0.14, 0.20), "L": (0.22, 0.35)}
SUCCESS_TALES = ["Ils reviennent les bras chargés de bonbons !", "Mission accomplie : le trésor est à toi !",
                 "Tes monstres ont pillé une crypte entière !"]
FAIL_TALES = ["Ils reviennent bredouilles… et un peu effrayés.", "Un chasseur de monstres les a fait fuir !",
              "Ils se sont perdus dans le brouillard."]
MAX_TEAM = 3


def team_odds(dest: dict, cards: list[str]) -> tuple[float, float]:
    """(success chance, reward multiplier) for a team of card keys."""
    chance, mult = dest["chance"], 1.0
    for key in cards:
        c, m = RARITY_BONUS[CARD[key]["rarity"]]
        chance += c
        mult += m
    return min(0.97, chance), mult


def meta_key(g, u):
    return f"exp:{g}:{u}"


class ExpeditionView(GameView):
    banner_key = "manor"
    kicker = "EXPÉDITIONS"
    owner_hint = "Gère tes propres expéditions avec /expedition."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=600)
        self.dest = "forest"
        self.team: list[str] = []
        self.report = ""

    @property
    def trip(self):
        return self.store.meta_get(meta_key(self.guild_id, self.owner_id))

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        p = Panel("purple").banner(self.banner_key)
        trip = self.trip
        if trip:
            d = DEST[trip["dest"]]
            team = " ".join(E(CARD[k]["emoji"]) for k in trip["team"])
            back = trip["ends"] <= time.time()
            p.title(d["name"], icon=d["emoji"],
                    body=f"{team} · *{d['story']}*\n"
                         + (f"{E.check} **Ton équipe est revenue !** Va voir ce qu'elle rapporte."
                            if back else f"{E.hourglass} Retour {relative(trip['ends'])}")
                         + f"\n-# Chances de réussite : **{round(trip['chance'] * 100)} %** · butin ×{trip['mult']:.2f}")
            p.sep()
            p.row(button("Accueillir l'équipe" if back else "Encore en route…", "chest", "success", self._claim,
                         disabled=not back),
                  nav("cards", u, "Mes cartes", "gift"), nav("hub", u, "Tous les jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        owned = self.store.cards(g, u)
        if self.report:
            p.text(self.report)
            p.sep()
        if not owned:
            p.title("Ton armée est vide", icon="gift",
                    body="Pour partir en expédition, il te faut des **monstres** ! Ouvre des boosters dans "
                         f"{E.gift} **Cartes maudites** : chaque carte peut rejoindre une équipe.")
            p.row(nav("cards", u, "Ouvrir des boosters", "gift", "success"), nav("hub", u, "Tous les jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        d = DEST[self.dest]
        chance, mult = team_odds(d, self.team)
        lo, hi = d["reward"]
        p.title("Prépare ton expédition", icon="key",
                body="Choisis une destination et jusqu'à **3 monstres** de ta collection. Plus ils sont rares, "
                     "plus la mission a de chances de réussir… et plus le butin est gros.")
        p.sep()
        lines = []
        for dd in DESTINATIONS:
            mark = "▸ " if dd["key"] == self.dest else ""
            dur = f"{dd['minutes']} min" if dd["minutes"] < 60 else f"{dd['minutes'] // 60} h"
            extra = f" · {round(dd['booster'] * 100)} % booster" if dd["booster"] else ""
            lines.append(f"{mark}{E(dd['emoji'])} **{dd['name']}** — {dur} · {dd['reward'][0]}-{dd['reward'][1]} "
                         f"{E.candy}{extra}")
        p.text("\n".join(lines))
        team = " ".join(f"{E(CARD[k]['emoji'])} {CARD[k]['name']}" for k in self.team) or "*personne*"
        p.text(f"**Équipe :** {team}\n{E.bar(chance, 1, 8)} réussite **{round(chance * 100)} %** · butin "
               f"**{int(lo * mult)}-{int(hi * mult)}** {E.candy}")
        p.row(*[button(dd["name"].split(" ")[0] + " " + dd["name"].split(" ")[-1], dd["emoji"],
                       "primary" if dd["key"] == self.dest else "secondary", self._pick(dd["key"]))
                for dd in DESTINATIONS])
        opts = [discord.SelectOption(label=CARD[k]["name"], value=k, emoji=E.partial(CARD[k]["emoji"]),
                                     description=f"{RARITIES[CARD[k]['rarity']]['name']}",
                                     default=k in self.team)
                for k in sorted(owned, key=lambda k: "LERC".index(CARD[k]["rarity"]))][:25]
        sel = discord.ui.Select(placeholder="Choisis ton équipe (1 à 3 monstres)…", min_values=1,
                                max_values=min(MAX_TEAM, len(opts)), options=opts)
        sel.callback = self._team
        p.row(sel)
        p.row(button("Lancer l'expédition", "lightning", "success", self._go, disabled=not self.team),
              nav("top_exp", u, "Classement", "trophy"))
        p.footer(self.footer())
        return p

    def _pick(self, key):
        async def cb(interaction):
            self.dest = key
            await self.refresh(interaction)
        return cb

    async def _team(self, interaction):
        owned = self.store.cards(self.guild_id, self.owner_id)
        self.team = [k for k in interaction.data["values"] if k in owned][:MAX_TEAM]
        await self.refresh(interaction)

    async def _go(self, interaction):
        async with self.lock:
            g, u = self.guild_id, self.owner_id
            if self.trip or not self.team:
                return await self.refresh(interaction)
            d = DEST[self.dest]
            chance, mult = team_odds(d, self.team)
            self.store.meta_set(meta_key(g, u), dict(dest=d["key"], team=self.team, chance=chance, mult=mult,
                                                      ends=time.time() + d["minutes"] * 60))
            self.report = ""
            await self.refresh(interaction)

    async def _claim(self, interaction):
        async with self.lock:
            g, u = self.guild_id, self.owner_id
            trip = self.trip
            if not trip or trip["ends"] > time.time():
                return await self.refresh(interaction)
            self.store.meta_del(meta_key(g, u))
            d = DEST[trip["dest"]]
            if random.random() < trip["chance"]:
                amount = int(random.randint(*d["reward"]) * trip["mult"])
                extra = ""
                if random.random() < d["booster"]:
                    self.store.give_item(g, u, "booster")
                    extra = f"\n{E.gift} Ils ramènent aussi un **booster de cartes** !"
                r = grant(self.store, g, u, amount, d["xp"], "expedition", stats={"exp_win": 1})
                self.report = f"### {E.trophy} {random.choice(SUCCESS_TALES)}\n{r.line()}{extra}"
            else:
                consolation = d["reward"][0] // 5
                r = grant(self.store, g, u, consolation, d["xp"] // 3, "expedition", stats={"exp_fail": 1})
                self.report = f"### {E.skull} {random.choice(FAIL_TALES)}\n{r.line()}"
            self.team = [k for k in trip["team"] if k in self.store.cards(g, u)]
            await self.refresh(interaction)


class Expedition(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["manor"] = self.open
        bot.openers["expedition"] = self.open

    async def open(self, interaction, edit=False):
        await ExpeditionView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="expedition", description="🗺️ Envoie tes monstres en expédition et rapporte du butin")
    @app_commands.guild_only()
    async def expedition(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Expedition(bot))
