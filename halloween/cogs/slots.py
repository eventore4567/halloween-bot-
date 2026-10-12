"""/machine — the haunted slot machine: three neon reels, pull the lever."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import neon
from ..art import slots as art
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

# name, weight on each reel, multiplier for three in a row, neon colour
SYMBOLS = [
    ("pumpkin", 8, 5, neon.ORANGE),
    ("bat", 7, 7, neon.PURPLE),
    ("ghost", 6, 11, neon.WHITE),
    ("skull", 4, 22, neon.CYAN),
    ("crystal", 3, 40, neon.PINK),
    ("crown", 1, 150, neon.YELLOW),
]
PAIR = 1.1  # two identical symbols: a little more than the bet back
BETS = [10, 50, 100, 250]
GIF_NAME, PNG_NAME = "machine.gif", "machine.png"
NAMES = [s[0] for s in SYMBOLS]
COLORS = {s[0]: s[3] for s in SYMBOLS}
MULT = {s[0]: s[2] for s in SYMBOLS}


def spin(rnd=random) -> tuple[str, str, str]:
    weights = [s[1] for s in SYMBOLS]
    return tuple(rnd.choices(NAMES, weights)[0] for _ in range(3))


def payout(result, bet: int) -> tuple[int, str]:
    """Candies won and a short label."""
    a, b, c = result
    if a == b == c:
        return bet * MULT[a], ("JACKPOT ×%d" % MULT[a]) if a == "crown" else ("TRIPLE ×%d" % MULT[a])
    if a == b or b == c or a == c:
        return int(bet * PAIR), "PAIRE"
    return 0, ""


def expected_return() -> float:
    total = sum(s[1] for s in SYMBOLS)
    p = {s[0]: s[1] / total for s in SYMBOLS}
    out = 0.0
    for a in NAMES:
        for b in NAMES:
            for c in NAMES:
                out += p[a] * p[b] * p[c] * payout((a, b, c), 1000)[0] / 1000
    return out


class SlotsView(GameView):
    banner_key = "slots"
    kicker = "MACHINE HANTÉE"
    owner_hint = "Joue sur ta propre machine avec /machine."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.state = "bet" if allowed else "empty"
        self.bet = 50
        self.result = None
        self.won = 0
        self.label = ""
        self.reward = None
        self.token = 0
        self.spins = 0
        self._still = b""

    def build(self) -> Panel:
        p = Panel("purple")
        if self.state in ("bet", "empty") and not self.spins:
            p.banner(self.banner_key)
        elif self.state == "spin":
            p.image(GIF_NAME)
        else:
            p.image(PNG_NAME)
        g, u = self.guild_id, self.owner_id
        left = self.store.remaining(g, u, "slots")
        if self.state == "empty":
            p.title("La machine est à court de jetons", icon="lock",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "spin":
            p.title("Les rouleaux tournent…", icon="gem",
                    body=f"Mise : **{config.fmt(self.bet)}** {E.candy} · *croise les doigts…*")
            p.footer(self.footer())
            return p
        if self.spins:
            names = " ".join(E(n) for n in self.result)
            if self.won > self.bet:
                head = f"{E.sparkle} **{self.label}** — tu gagnes **{config.fmt(self.won)}** {E.candy} !"
            elif self.won:
                head = f"{E.check} **Paire** — tu récupères **{config.fmt(self.won)}** {E.candy}."
            else:
                head = f"{E.cross} Rien cette fois… la machine garde ta mise."
            body = f"{names}\n{head}" + (f"\n{self.reward.line()}" if self.reward and self.reward.line() else "")
            p.title("Résultat", icon="gem", body=body)
        else:
            table = " · ".join(f"{E(n)}×{MULT[n]}" for n in NAMES)
            p.title("La Machine hantée", icon="gem",
                    body=f"Choisis ta mise et **tire le levier** !\n**Trois identiques** : {table}\n"
                         f"**Deux identiques** : ta mise ×{PAIR:g}")
        p.sep()
        bal = self.store.candies(g, u)
        p.text(f"{E.candy_bag} Mise : **{config.fmt(self.bet)}** {E.candy} · tours restants ce soir : **{left}**")
        p.row(*[button(str(b), "candy", "primary" if b == self.bet else "secondary", self._set_bet(b), disabled=b > bal)
                for b in BETS])
        p.row(button("Tirer le levier !", "lightning", "success", self._pull, disabled=bal < self.bet or not left),
              nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    def _set_bet(self, amount):
        async def cb(interaction):
            if self.state == "spin":
                return await interaction.response.defer()
            self.bet = amount
            await self.refresh(interaction)
        return cb

    async def _pull(self, interaction):
        async with self.lock:
            if self.state == "spin":
                return await interaction.response.defer()
            g, u = self.guild_id, self.owner_id
            try:
                self.store.spend(g, u, self.bet, "machine")
            except NotEnough:
                return await self.refresh(interaction)
            if not self.store.use_play(g, u, "slots"):
                self.store.add_candies(g, u, self.bet, "machine-rembourse", boost=False)
                self.state = "empty"
                return await self.refresh(interaction)
            await interaction.response.defer()
            self.result = spin()
            self.won, self.label = payout(self.result, self.bet)
            triple = len(set(self.result)) == 1
            stats = {"slots_win": 1} if triple else None
            best = {"slots_jackpot": 1} if self.result[0] == "crown" and triple else None
            self.reward = grant(self.store, g, u, self.won, 3 + (10 if triple else 0), "machine", stats=stats, best=best)
            win_color = (neon.YELLOW if self.result[0] == "crown" else neon.GREEN) if triple else (
                neon.CYAN if self.won else None)
            suspense = self.result[0] == self.result[1]
            data, seconds, still = await asyncio.to_thread(
                art.spin_gif, self.result, NAMES, COLORS, self.label or None, win_color, suspense, random.randrange(10**6))
            self._still = still
            self.spins += 1
            self.state = "spin"
            self.token += 1
            await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
            self._arm(seconds + 0.3, self.token)

    def _arm(self, delay, token):
        async def later():
            await asyncio.sleep(delay)
            await self._show(token)
        asyncio.create_task(later())

    async def _show(self, token):
        async with self.lock:
            if self.state == "spin" and self.token == token:
                self.state = "bet"
                await self.push(attachments=[image_file(self._still, PNG_NAME)])


class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["slots"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.remaining(interaction.guild_id, interaction.user.id, "slots") > 0
        await SlotsView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="machine", description="🎰 La Machine hantée : tire le levier et aligne les monstres")
    @app_commands.guild_only()
    async def machine(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Slots(bot))
