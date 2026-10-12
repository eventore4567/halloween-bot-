"""/roulette — six potions, one is poisoned: every safe sip raises the pot. Cash out before the poison."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import neon
from ..art import roulette as art
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

LADDER = [1.2, 1.5, 2.0, 2.8, 4.5]  # pot multiplier after 1..5 safe sips
BETS = [25, 100, 250, 500]
GIF_NAME, PNG_NAME = "roulette.gif", "roulette.png"


class RouletteView(GameView):
    banner_key = "roulette"
    kicker = "ROULETTE DES POTIONS"
    owner_hint = "Lance ta propre roulette avec /roulette."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.state = "bet" if allowed else "empty"
        self.bet = 100
        self.poison = random.randrange(6)
        self.states = ["full"] * 6
        self.sips = 0
        self.flash = ""
        self.reward = None
        self.animating = False
        self.anim = 0

    def pot(self) -> int:
        return int(self.bet * LADDER[self.sips - 1]) if self.sips else self.bet

    def build(self) -> Panel:
        p = Panel("green")
        if self.state in ("bet", "empty"):
            p.banner(self.banner_key)
        else:
            p.image(GIF_NAME if self.animating else PNG_NAME)
        if self.state == "empty":
            p.title("L'apothicaire a fermé boutique", icon="lock",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        ladder = " → ".join(f"×{m:g}" for m in LADDER)
        if self.state == "bet":
            p.title("La Roulette des potions", icon="potion_green",
                    body=f"Six fioles, **une seule est empoisonnée**. Chaque gorgée sans poison fait grimper ton pot : "
                         f"{ladder}.\nEncaisse quand tu veux… mais si tu tombes sur le poison, tu perds tout !")
            bal = self.store.candies(self.guild_id, self.owner_id)
            p.row(*[button(str(b), "candy", "primary" if b == self.bet else "secondary", self._set_bet(b),
                           disabled=b > bal) for b in BETS])
            p.row(button("Prendre place", "potion_green", "success", self._begin, disabled=bal < self.bet))
        elif self.state == "play":
            nxt = LADDER[self.sips] if self.sips < len(LADDER) else None
            body = (f"Mise **{config.fmt(self.bet)}** {E.candy} · pot actuel **{config.fmt(self.pot())}** {E.candy}"
                    + (f" · prochaine gorgée : **×{nxt:g}**" if nxt else ""))
            if self.flash:
                body = self.flash + "\n" + body
            p.title(f"Gorgée {self.sips + 1}", icon="potion_purple", body=body)
            p.rows([button(str(i + 1), "potion_gold", "secondary", self._drink(i), disabled=s != "full" or self.animating)
                    for i, s in enumerate(self.states)], per_row=3)
            p.row(button(f"Encaisser {config.fmt(self.pot())}", "candy_bag", "success", self._cash,
                         disabled=not self.sips or self.animating))
        else:
            won = self.state == "cashed"
            p.title("Pot encaissé !" if won else "Empoisonné…", icon="sparkle" if won else "skull",
                    body=(self.flash + "\n" if self.flash else "") + self.reward.line())
            left = self.store.remaining(self.guild_id, self.owner_id, "roulette")
            p.row(nav("roulette", self.owner_id, f"Rejouer ({left})", "potion_green", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    def _set_bet(self, amount):
        async def cb(interaction):
            if self.state == "bet":
                self.bet = amount
            await self.refresh(interaction)
        return cb

    async def _begin(self, interaction):
        async with self.lock:
            if self.state != "bet":
                return await interaction.response.defer()
            g, u = self.guild_id, self.owner_id
            try:
                self.store.spend(g, u, self.bet, "roulette")
            except NotEnough:
                return await self.refresh(interaction)
            if not self.store.use_play(g, u, "roulette"):
                self.store.add_candies(g, u, self.bet, "roulette-rembourse", boost=False)
                self.state = "empty"
                return await self.refresh(interaction)
            self.state = "play"
            await interaction.response.defer()
            data = await asyncio.to_thread(art.shelf_png, self.states)
            await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])

    def _drink(self, index: int):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or self.animating or self.states[index] != "full":
                    return await interaction.response.defer()
                await interaction.response.defer()
                poisoned = index == self.poison
                if poisoned:
                    label = "EMPOISONNÉ !"
                    self.flash = f"{E.skull} La fiole **{index + 1}** était empoisonnée ! Ton pot s'évapore."
                    self._end(False)
                else:
                    self.sips += 1
                    label = f"POT ×{LADDER[self.sips - 1]:g}"
                    self.flash = f"{E.check} Ouf, la fiole **{index + 1}** était saine !"
                    if self.sips >= len(LADDER):  # only the poison remains: auto cash out
                        self.flash += f"\n{E.trophy} Il ne reste que le poison : le pot est encaissé automatiquement !"
                        self._end(True)
                data, seconds = await asyncio.to_thread(art.drink_gif, self.states, index, poisoned, label)
                self.states[index] = "poison" if poisoned else "empty"
                if self.state != "play":
                    self.states[self.poison] = "poison"
                still = await asyncio.to_thread(art.shelf_png, self.states, label,
                                                neon.GREEN if poisoned else neon.YELLOW)
                self.animating = True
                self.anim += 1
                anim = self.anim
                await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.anim == anim:
                    self.animating = False
                    await self.push(attachments=[image_file(still, PNG_NAME)])
        return cb

    async def _cash(self, interaction):
        async with self.lock:
            if self.state != "play" or not self.sips or self.animating:
                return await interaction.response.defer()
            self.flash = f"{E.sparkle} Tu reposes la fiole et empoches **{config.fmt(self.pot())}** {E.candy}."
            self._end(True)
            self.states[self.poison] = "poison"
            await interaction.response.defer()
            data = await asyncio.to_thread(art.shelf_png, self.states, "ENCAISSÉ", neon.YELLOW)
            await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])

    def _end(self, cashed: bool):
        self.state = "cashed" if cashed else "poisoned"
        self.reward = grant(self.store, self.guild_id, self.owner_id, self.pot() if cashed else 0,
                            4 + 3 * self.sips, "roulette", stats={"roulette_sips": self.sips},
                            best={"roulette_best": self.sips})
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self._end(bool(self.sips))


class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["roulette"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.remaining(interaction.guild_id, interaction.user.id, "roulette") > 0
        await RouletteView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="roulette", description="🧪 La Roulette des potions : une fiole sur six est empoisonnée")
    @app_commands.guild_only()
    async def roulette(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Roulette(bot))
