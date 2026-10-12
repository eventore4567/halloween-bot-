"""/pendu — guess the spooky word before the skeleton is complete."""
from __future__ import annotations

import random
import string

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content.games import HANGMAN, strip_accents
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

LIVES = 7
STAGES = [
    "  ┌───┐\n  │   \n  │   \n  │   \n ═╧═",
    "  ┌───┐\n  │   💀\n  │   \n  │   \n ═╧═",
    "  ┌───┐\n  │   💀\n  │   │\n  │   \n ═╧═",
    "  ┌───┐\n  │   💀\n  │  ╱│\n  │   \n ═╧═",
    "  ┌───┐\n  │   💀\n  │  ╱│╲\n  │   \n ═╧═",
    "  ┌───┐\n  │   💀\n  │  ╱│╲\n  │  ╱ \n ═╧═",
    "  ┌───┐\n  │   💀\n  │  ╱│╲\n  │  ╱ ╲\n ═╧═",
    "  ┌───┐\n  │   ☠️\n  │  ╱│╲\n  │  ╱ ╲\n ═╧═",
]


def reveal(word: str, guessed: set[str]) -> str:
    out = []
    for ch in word:
        base = strip_accents(ch).upper()
        if not base.isalpha():
            out.append("  " if ch == " " else ch)
        elif base in guessed:
            out.append(ch)
        else:
            out.append("_")
    return " ".join(out)


def solved(word: str, guessed: set[str]) -> bool:
    return all((not strip_accents(c).isalpha()) or strip_accents(c).upper() in guessed for c in word)


def hangman_reward(lives_left: int) -> int:
    return 40 + 15 * lives_left


class GuessModal(discord.ui.Modal, title="Proposer le mot"):
    guess = discord.ui.TextInput(label="Ta réponse", placeholder="Ex : CITROUILLE", max_length=40)

    def __init__(self, view: "HangmanView"):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.view.full_guess(interaction, str(self.guess.value))


class HangmanView(GameView):
    banner_key = "hangman"
    kicker = "LE PENDU"
    owner_hint = "Lance ta propre partie avec /pendu."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.word, self.hint = random.choice(HANGMAN)
        self.guessed: set[str] = set()
        self.misses = 0
        self.state = "play" if allowed else "empty"
        self.reward = None
        self.flash = ""

    def build(self) -> Panel:
        p = Panel("green").banner(self.banner_key)
        if self.state == "empty":
            p.title("Le bourreau se repose", icon="hourglass",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        lives = LIVES - self.misses
        if self.state == "won":
            p.title("Squelette sauvé !", icon="sparkle", body=f"Le mot était **{self.word}**.\n{self.reward.line()}")
        elif self.state == "lost":
            p.title("Trop tard…", icon="skull", body=f"Le mot était **{self.word}**.")
        else:
            p.title("Le Pendu de la crypte", icon="skull",
                    body=f"{E.scroll} Indice : *{self.hint}* · {len([c for c in self.word if c.isalpha()])} lettres")
        shown = self.word if self.state != "play" else reveal(self.word, self.guessed)
        p.text(f"```\n{STAGES[min(self.misses, LIVES)]}\n```\n## `{shown}`")
        wrong = sorted(l for l in self.guessed if l not in strip_accents(self.word).upper())
        p.text(f"Vies : {E.heart * lives}{E.bar_m0 * self.misses}"
               + (f"\n-# Lettres ratées : {' '.join(wrong)}" if wrong else "")
               + (f"\n{self.flash}" if self.flash else ""))
        p.sep()
        if self.state == "play":
            for chunk in (string.ascii_uppercase[:13], string.ascii_uppercase[13:]):
                opts = [discord.SelectOption(label=c, value=c) for c in chunk if c not in self.guessed]
                if not opts:
                    continue
                sel = discord.ui.Select(placeholder=f"Lettres {chunk[0]} à {chunk[-1]}", options=opts)
                sel.callback = self._letter
                p.row(sel)
            p.row(button("Proposer le mot", "scroll", "primary", self._modal),
                  button("Abandonner", "cross", "danger", self._giveup))
        else:
            left = self.store.remaining(self.guild_id, self.owner_id, "hangman")
            p.row(nav("hangman", self.owner_id, f"Rejouer ({left})", "skull", "success"),
                  nav("quiz", self.owner_id, "Quiz", "crystal"), nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _letter(self, interaction):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            letter = interaction.data["values"][0]
            self.guessed.add(letter)
            if letter in strip_accents(self.word).upper():
                count = strip_accents(self.word).upper().count(letter)
                self.flash = f"{E.check} **{letter}** est dans le mot ({count}×) !"
                if solved(self.word, self.guessed):
                    self._win()
            else:
                self.misses += 1
                self.flash = f"{E.cross} Pas de **{letter}**…"
                if self.misses >= LIVES:
                    self._lose()
            await self.refresh(interaction)

    async def _modal(self, interaction):
        if self.state != "play":
            return await interaction.response.defer()
        await interaction.response.send_modal(GuessModal(self))

    async def full_guess(self, interaction, text: str):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            norm = lambda s: strip_accents(s).upper().replace("-", " ").strip()
            if norm(text) == norm(self.word):
                self.guessed.update(c for c in strip_accents(self.word).upper() if c.isalpha())
                self._win(bonus=True)
            else:
                self.misses = min(LIVES, self.misses + 2)
                self.flash = f"{E.cross} « {text[:30]} » n'est pas le bon mot (-2 vies)."
                if self.misses >= LIVES:
                    self._lose()
            await interaction.response.edit_message(view=self._rendered())

    def _rendered(self):
        self.render()
        return self

    def _win(self, bonus=False):
        self.state = "won"
        g, u = self.guild_id, self.owner_id
        amount = hangman_reward(LIVES - self.misses) + (30 if bonus else 0)
        self.reward = grant(self.store, g, u, amount, 15, "pendu", stats={"hangman_win": 1})
        self.flash = f"{E.lightning} Mot trouvé d'un coup : **+30** bonus !" if bonus else ""
        self.finish()

    def _lose(self):
        self.state = "lost"
        grant(self.store, self.guild_id, self.owner_id, 0, 3, "pendu")
        self.flash = ""
        self.finish()

    async def _giveup(self, interaction):
        async with self.lock:
            if self.state == "play":
                self.misses = LIVES
                self._lose()
            await self.refresh(interaction)

    def on_expire(self):
        if self.state == "play":
            self.state = "lost"


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["hangman"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "hangman")
        await HangmanView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="pendu", description="💀 Le pendu de la crypte : trouve le mot d'Halloween")
    @app_commands.guild_only()
    async def pendu(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Hangman(bot))
