"""/plusoumoins — will the next monster card be higher or lower? Cash out before you fall."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import hilo as art
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

START_POT = 25
MAX_STREAK = 8
GIF_NAME, PNG_NAME = "plusoumoins.gif", "plusoumoins.png"


def multiplier(value: int, higher: bool) -> float | None:
    """Pot multiplier for a right guess; None when the guess cannot win (ties are replayed)."""
    count = 13 - value if higher else value - 1
    if count <= 0:
        return None
    return max(1.05, round(0.94 * 12 / count, 2))


class HiloView(GameView):
    banner_key = None
    kicker = "PLUS OU MOINS"
    owner_hint = "Lance ta propre partie avec /plusoumoins."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.state = "play" if allowed else "empty"
        if not allowed:
            self.banner_key = "hilo"
        self.current = random.randint(1, 13)
        self.pot = START_POT
        self.streak = 0
        self.flash = ""
        self.reward = None
        self.animating = False
        self.anim = 0

    def build(self) -> Panel:
        p = Panel("cyan")
        if self.state == "empty":
            p.banner("hilo")
            p.title("Le croupier fantôme est parti dormir", icon="lock",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        p.image(GIF_NAME if self.animating else PNG_NAME)
        if self.state == "play":
            body = (f"La prochaine carte sera-t-elle **plus haute** ou **plus basse** que **{self.current}** ?\n"
                    f"{E.candy_bag} Pot : **{config.fmt(self.pot)}** {E.candy} · série **{self.streak}/{MAX_STREAK}** · "
                    f"égalité = on rejoue")
            if self.flash:
                body = self.flash + "\n" + body
            p.title("Plus ou Moins", icon="star", body=body)
            hi, lo = multiplier(self.current, True), multiplier(self.current, False)
            p.row(button(f"Plus ×{hi:g}" if hi else "Plus", "fire", "success", self._guess(True), disabled=hi is None),
                  button(f"Moins ×{lo:g}" if lo else "Moins", "moon", "danger", self._guess(False), disabled=lo is None),
                  button(f"Encaisser {config.fmt(self.pot)}", "candy_bag", "primary", self._cash,
                         disabled=self.streak == 0))
        else:
            won = self.state == "cashed"
            p.title("Pot encaissé !" if won else "Perdu…", icon="sparkle" if won else "skull",
                    body=(self.flash + "\n" if self.flash else "")
                    + f"Série : **{self.streak}** bonne{'s' if self.streak > 1 else ''} réponse{'s' if self.streak > 1 else ''}\n"
                    + self.reward.line())
            left = self.store.remaining(self.guild_id, self.owner_id, "hilo")
            p.row(nav("hilo", self.owner_id, f"Rejouer ({left})", "star", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def extra_files(self):
        if self.state == "empty":
            return []
        data = await asyncio.to_thread(art.table_png, self.current, self.streak, self.pot)
        return [image_file(data, PNG_NAME)]

    def _guess(self, higher: bool):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or multiplier(self.current, higher) is None:
                    return await interaction.response.defer()
                await interaction.response.defer()
                old, nxt = self.current, random.randint(1, 13)
                if nxt == old:
                    verdict = "ÉGALITÉ"
                    self.flash = f"{E.question} **{nxt}** — égalité, on rejoue !"
                elif (nxt > old) == higher:
                    verdict = "GAGNÉ"
                    self.pot = round(self.pot * multiplier(old, higher))
                    self.streak += 1
                    self.flash = f"{E.check} **{nxt}** — bien vu ! Le pot monte à **{config.fmt(self.pot)}** {E.candy}."
                    if self.streak >= MAX_STREAK:
                        self._end(True)
                        self.flash += f"\n{E.trophy} Série maximale : le pot est encaissé automatiquement !"
                else:
                    verdict = "PERDU"
                    self.flash = f"{E.cross} **{nxt}** — raté, le pot de **{config.fmt(self.pot)}** {E.candy} s'envole."
                    self._end(False)
                data, seconds = await asyncio.to_thread(art.flip_gif, old, nxt, self.streak, self.pot, verdict)
                self.current = nxt
                self.animating = True
                self.anim += 1
                anim = self.anim
                await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
                if self.state == "play":
                    still = await asyncio.to_thread(art.table_png, self.current, self.streak, self.pot)
                else:
                    still = await asyncio.to_thread(art.result_png, old, nxt, self.streak, self.pot, verdict)
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.anim == anim:
                    self.animating = False
                    await self.push(attachments=[image_file(still, PNG_NAME)])
        return cb

    async def _cash(self, interaction):
        async with self.lock:
            if self.state != "play" or not self.streak:
                return await interaction.response.defer()
            self.flash = ""
            self._end(True)
            await self.refresh(interaction)

    def _end(self, cashed: bool):
        self.state = "cashed" if cashed else "lost"
        self.reward = grant(self.store, self.guild_id, self.owner_id, self.pot if cashed else 0, 4 + 3 * self.streak,
                            "plusoumoins", stats={"hilo_right": self.streak}, best={"hilo_best": self.streak})
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self._end(bool(self.streak))


class Hilo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["hilo"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "hilo")
        await HiloView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="plusoumoins", description="🃏 Plus ou Moins : devine la prochaine carte et fais grossir le pot")
    @app_commands.guild_only()
    async def plusoumoins(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Hilo(bot))
