"""/formule — crack the cauldron's secret 4-ingredient code (Mastermind)."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content.games import ING, POTION, POTIONS
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

CODE_LEN = 4
TRIES = 8
FORMULA_INGREDIENTS = ["eye", "frog", "bone", "mushroom", "spider", "bat"]


def score(secret: list[str], guess: list[str]) -> tuple[int, int]:
    """(well placed, present elsewhere) — classic Mastermind feedback."""
    exact = sum(1 for a, b in zip(secret, guess) if a == b)
    common = sum(min(secret.count(x), guess.count(x)) for x in set(guess))
    return exact, common - exact


def formula_reward(tries_used: int) -> int:
    return max(50, 260 - 30 * (tries_used - 1))


def apply_potion(store, g, u, key) -> str:
    """Apply a potion's effect, return a short French description."""
    effect = POTION[key]["effect"]
    if effect == "show1":
        store.bump(g, u, "quiz_bonus", amount=1)
        return f"{E.potion_blue} **+1 émission** du Grand Frisson ce soir !"
    if effect == "luck30":
        until = store.add_effect(g, u, "luck", 1800)
        return f"{E.potion_gold} Tes gains de bonbons sont **doublés** jusqu'à {relative(until)} !"
    if effect == "souls":
        store.give_item(g, u, "booster")
        return f"{E.gift} Un **booster de cartes** apparaît dans la fumée !"
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
        return f"{E.shield} **1 bouclier** ajouté à ton sac !"
    if effect == "ticket":
        store.give_item(g, u, "ticket", 1)
        return f"{E.wheel} **1 ticket de roue** ajouté à ton sac !"
    return ""


class FormulaView(GameView):
    banner_key = "cauldron"
    kicker = "LA FORMULE"
    owner_hint = "Lance ta propre formule avec /formule."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=480)
        self.secret = random.sample(FORMULA_INGREDIENTS, CODE_LEN)
        self.current: list[str] = []
        self.history: list[tuple[list[str], int, int]] = []
        self.state = "play" if allowed else "empty"
        self.reward = None
        self.potion = None
        self.effect = ""

    def _line(self, guess, exact, near, n):
        icons = " ".join(E(ING[k]["emoji"]) for k in guess)
        return f"`{n:>2}`  {icons}   ⟶   {E.check}×**{exact}**  {E.sparkle}×**{near}**"

    def build(self) -> Panel:
        p = Panel("green").banner(self.banner_key)
        if self.state == "empty":
            p.title("Le chaudron refroidit", icon="cauldron",
                    body=f"Tu as épuisé tes formules. Le feu se rallume {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        hist = "\n".join(self._line(g, e, n, i + 1) for i, (g, e, n) in enumerate(self.history))
        if self.state == "won":
            pot = POTION[self.potion]
            n = len(self.history)
            p.title(f"Formule trouvée en {n} essai{'s' if n > 1 else ''} !", icon=pot["emoji"],
                    body=f"{hist}\n\nLe chaudron s'illumine et produit : **{pot['name']}**\n{self.effect}\n"
                         f"{self.reward.line()}")
        elif self.state == "lost":
            code = " ".join(E(ING[k]["emoji"]) for k in self.secret)
            p.title("Le chaudron explose…", icon="skull",
                    body=f"{hist}\n\nLa formule secrète était : {code}\n{self.reward.line()}")
        else:
            legend = f"{E.check} bon ingrédient **bien placé** · {E.sparkle} bon ingrédient **mal placé**"
            p.title("Déchiffre la formule secrète", icon="cauldron",
                    body=f"Le chaudron cache une formule de **{CODE_LEN} ingrédients différents**. "
                         f"Tu as **{TRIES} essais** pour la retrouver.\n-# {legend}")
            p.sep()
            slots = [E(ING[k]["emoji"]) for k in self.current] + [E.question] * (CODE_LEN - len(self.current))
            p.text((hist + "\n\n" if hist else "") + f"**Essai {len(self.history) + 1}/{TRIES}** : {' '.join(slots)}")
            btns = [button(ING[k]["name"].split(" ")[0], ING[k]["emoji"], "secondary", self._add(k),
                           disabled=k in self.current) for k in FORMULA_INGREDIENTS]
            p.row(*btns[:3])
            p.row(*btns[3:])
            p.row(button("Effacer", "cross", "danger", self._clear, disabled=not self.current))
        if self.state in ("won", "lost"):
            left = self.store.remaining(self.guild_id, self.owner_id, "cauldron")
            p.row(nav("cauldron", self.owner_id, f"Nouvelle formule ({left})", "cauldron", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    def _add(self, key):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or key in self.current:
                    return await interaction.response.defer()
                self.current.append(key)
                if len(self.current) == CODE_LEN:
                    self._submit()
                await self.refresh(interaction)
        return cb

    async def _clear(self, interaction):
        self.current = []
        await self.refresh(interaction)

    def _submit(self):
        guess, self.current = self.current, []
        exact, near = score(self.secret, guess)
        self.history.append((guess, exact, near))
        g, u = self.guild_id, self.owner_id
        if exact == CODE_LEN:
            self.state = "won"
            self.reward = grant(self.store, g, u, formula_reward(len(self.history)), 20, "formule",
                                stats={"potions": 1})
            self.potion = random.choice(POTIONS)["key"]
            self.effect = apply_potion(self.store, g, u, self.potion)
            self.finish()
        elif len(self.history) >= TRIES:
            self.state = "lost"
            self.reward = grant(self.store, g, u, 0, 5, "formule")
            self.finish()

    def on_expire(self):
        if self.state == "play":
            self.state = "lost"
            self.reward = grant(self.store, self.guild_id, self.owner_id, 0, 0, "formule")


class Formula(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["cauldron"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "cauldron")
        await FormulaView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="formule", description="🧪 La Formule : déchiffre le code secret du chaudron en 8 essais")
    @app_commands.guild_only()
    async def formule(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Formula(bot))
