"""/roue — wheel of fortune with an animated spin, free every 4 hours."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import cards as art
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

SPIN_FILE = "roue.gif"


def spin(rnd=random) -> int:
    return rnd.choices(range(len(config.WHEEL)), weights=[s["weight"] for s in config.WHEEL])[0]


def apply_segment(store, g, u, seg) -> str:
    kind = seg["kind"]
    if kind == "candy":
        r = grant(store, g, u, seg["value"], 10, "roue", stats={"jackpot": 1} if seg["value"] >= 1000 else None)
        return r.line()
    if kind == "xp":
        r = grant(store, g, u, 0, seg["value"], "roue")
        return r.line()
    if kind == "item":
        store.give_item(g, u, seg["value"])
        where = "`/cartes`" if seg["value"] == "booster" else "ton sac"
        return f"{E(seg['emoji'])} **{seg['label']}** ajouté à {where} !"
    return f"{E.pumpkin_angry} Une citrouille pourrie… Pas de chance cette fois !"


class WheelView(GameView):
    banner_key = "wheel"
    owner_hint = "Fais tourner ta propre roue avec /roue."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.state = "idle"
        self.target = None
        self.result_text = ""

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        p = Panel("gold")
        if self.state in ("spinning", "done"):
            p.image(SPIN_FILE)
        else:
            p.banner(self.banner_key)
        left = self.store.cooldown_left(g, u, "wheel")
        tickets = self.store.item_qty(g, u, "ticket")
        if self.state == "spinning":
            p.title("La roue tourne…", icon="wheel", body=f"{E.sparkle} Croise les doigts… {E.sparkle}")
        elif self.state == "done":
            seg = config.WHEEL[self.target]
            p.title(seg["label"], icon=seg["emoji"], thumb=E.url(seg["emoji"]), body=self.result_text)
        else:
            lines = [f"{E(s['emoji'])} {s['label']}" for s in config.WHEEL]
            p.title("Tente ta chance !", icon="wheel",
                    body="Un tour **gratuit toutes les 4 heures**. Les tickets permettent de rejouer sans attendre.")
            p.sep()
            p.text("### Ce que tu peux gagner\n" + " · ".join(lines))
        p.sep()
        status = (f"{E.check} **Ta roue est prête !**" if not left
                  else f"{E.hourglass} Prochain tour gratuit {relative(time.time() + left)}")
        if tickets:
            status += f" · {E.wheel} Tickets : **{tickets}**"
        p.text(status)
        busy = self.state == "spinning"
        btns = []
        if not left:
            btns.append(button("Tourner la roue", "wheel", "success", self._spin, disabled=busy))
        elif tickets:
            btns.append(button(f"Utiliser un ticket ({tickets})", "wheel", "primary", self._ticket, disabled=busy))
        else:
            btns.append(button("Reviens plus tard", "lock", "secondary", None, disabled=True))
        btns.append(nav("quiz", self.owner_id, "Quiz", "crystal"))
        btns.append(nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.row(*btns)
        p.footer(self.footer())
        return p

    async def _spin(self, interaction):
        async with self.lock:
            if self.state == "spinning":
                return await interaction.response.defer()
            if not self.store.take_cooldown(self.guild_id, self.owner_id, "wheel", config.WHEEL_COOLDOWN):
                return await self.refresh(interaction)
            await self._go(interaction)

    async def _ticket(self, interaction):
        async with self.lock:
            if self.state == "spinning":
                return await interaction.response.defer()
            if not self.store.use_item(self.guild_id, self.owner_id, "ticket"):
                return await self.refresh(interaction)
            await self._go(interaction)

    async def _go(self, interaction):
        await interaction.response.defer()
        g, u = self.guild_id, self.owner_id
        self.target = spin()
        seg = config.WHEEL[self.target]
        self.result_text = apply_segment(self.store, g, u, seg)
        self.store.stat_add(g, u, "wheel_spins")
        data = await asyncio.to_thread(art.wheel_gif, ("v1",), self.target)
        self.state = "spinning"
        await self.refresh(interaction, attachments=[image_file(data, SPIN_FILE)])
        await asyncio.sleep(3.4)
        self.state = "done"
        await self.push()


class Wheel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["wheel"] = self.open

    async def open(self, interaction, edit=False):
        await WheelView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="roue", description="🎡 La roue du destin : un tour gratuit toutes les 4 heures")
    @app_commands.guild_only()
    async def roue(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Wheel(bot))
