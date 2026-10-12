"""/bonneteau — follow the candy hidden under three shuffling neon pumpkins."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import shell as art
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

# (swaps, animation steps per swap, candies)
ROUNDS = [(4, 8, 35), (7, 6, 70), (11, 4, 130)]
PERFECT_BONUS = 80
GIF_NAME, PNG_NAME = "bonneteau.gif", "bonneteau.png"
PAIRS = [(0, 1), (1, 2), (0, 2)]


def make_swaps(count: int, rnd=random) -> list[tuple[int, int]]:
    """Random swaps, never the same pair twice in a row (it would look like nothing happened)."""
    out = []
    for _ in range(count):
        pair = rnd.choice([p for p in PAIRS if not out or set(p) != set(out[-1])])
        out.append(pair if rnd.random() < 0.5 else pair[::-1])
    return out


def shell_reward(correct: int) -> int:
    return sum(r[2] for r in ROUNDS[:correct]) + (PERFECT_BONUS if correct == len(ROUNDS) else 0)


class ShellView(GameView):
    banner_key = "shell"
    kicker = "LE BONNETEAU"
    owner_hint = "Lance ta propre partie avec /bonneteau."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.state = "ready" if allowed else "empty"
        self.round = 0
        self.correct = 0
        self.slot = 0
        self.flash = ""
        self.reward = None
        self.token = 0

    def build(self) -> Panel:
        p = Panel("orange")
        if self.state in ("ready", "empty"):
            p.banner(self.banner_key)
        else:
            p.image(GIF_NAME if self.state == "shuffle" else PNG_NAME)
        if self.state == "empty":
            p.title("Les citrouilles dorment", icon="pumpkin",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "ready":
            p.title("Le Bonneteau des Citrouilles", icon="pumpkin_lit",
                    body=f"Un {E.candy} se cache sous une citrouille… puis elles se mélangent !\n"
                         "**Suis-le des yeux** et désigne la bonne citrouille. 3 manches, de plus en plus rapides.\n"
                         f"-# Une erreur et c'est fini · {config.fmt(shell_reward(len(ROUNDS)))} bonbons pour un sans-faute")
            p.row(button("Mélanger !", "pumpkin_lit", "success", self._start))
        elif self.state == "shuffle":
            p.title(f"Manche {self.round}/{len(ROUNDS)} · ça mélange !", icon="eye",
                    body=(self.flash + "\n" if self.flash else "") + f"{E.candy} *Ne quitte pas le bonbon des yeux…*")
        elif self.state == "pick":
            p.title(f"Manche {self.round}/{len(ROUNDS)} · où est le bonbon ?", icon="question",
                    body="Choisis ta citrouille !")
            p.row(*[button(f"Citrouille {k + 1}", "pumpkin", "primary", self._pick(k)) for k in range(3)])
        else:
            won = self.correct == len(ROUNDS)
            p.title("Œil de lynx !" if won else "Raté…", icon="sparkle" if won else "skull",
                    body=(self.flash + "\n" if self.flash else "")
                    + f"Manches gagnées : **{self.correct}/{len(ROUNDS)}**\n{self.reward.line()}")
            left = self.store.remaining(self.guild_id, self.owner_id, "shell")
            p.row(nav("shell", self.owner_id, f"Rejouer ({left})", "pumpkin_lit", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _start(self, interaction):
        async with self.lock:
            if self.state != "ready":
                return await interaction.response.defer()
            await interaction.response.defer()
            await self._next_round(interaction)

    async def _next_round(self, interaction):
        self.round += 1
        swaps, steps, _candies = ROUNDS[self.round - 1]
        start = random.randrange(3)
        data, seconds, self.slot = await asyncio.to_thread(art.shuffle_gif, start, make_swaps(swaps), steps)
        self.state = "shuffle"
        self.token += 1
        await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
        self._arm(seconds + 0.6, self.token)

    def _arm(self, delay: float, token: int):
        async def later():
            await asyncio.sleep(delay)
            await self._ask(token)
        asyncio.create_task(later())

    async def _ask(self, token: int):
        async with self.lock:
            if self.state == "shuffle" and self.token == token:
                self.state = "pick"
                still = await asyncio.to_thread(art.still_png)
                await self.push(attachments=[image_file(still, PNG_NAME)])

    def _pick(self, choice: int):
        async def cb(interaction):
            async with self.lock:
                if self.state != "pick":
                    return await interaction.response.defer()
                if choice == self.slot:
                    self.correct += 1
                    self.flash = f"{E.check} Bien vu, le bonbon était sous la citrouille **{choice + 1}** !"
                    if self.round < len(ROUNDS):
                        await interaction.response.defer()
                        return await self._next_round(interaction)
                else:
                    self.flash = f"{E.cross} Vide ! Le bonbon était sous la citrouille **{self.slot + 1}**."
                self._end()
                await interaction.response.defer()
                data = await asyncio.to_thread(art.reveal_png, self.slot, choice)
                await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])
        return cb

    def _end(self):
        self.state = "end"
        self.reward = grant(self.store, self.guild_id, self.owner_id, shell_reward(self.correct), 5 + 5 * self.correct,
                            "bonneteau", stats={"shell_win": self.correct}, best={"shell_best": self.correct})
        self.finish()

    def on_expire(self):
        if self.state in ("shuffle", "pick"):
            self._end()


class Shell(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["shell"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "shell")
        await ShellView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="bonneteau", description="🎃 Le Bonneteau : suis le bonbon sous les citrouilles")
    @app_commands.guild_only()
    async def bonneteau(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Shell(bot))
