"""/motus — find the Halloween word in 6 tries: the first letter is given."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import motus as art
from ..content.games import strip_accents
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

WORDS = [
    ("SORCIERE", "Elle vole sur un balai"), ("FANTOME", "Il traverse les murs"), ("VAMPIRE", "Il dort dans un cercueil"),
    ("MOMIE", "Elle est enroulée de bandelettes"), ("ZOMBIE", "Un mort qui marche"), ("CRYPTE", "Caveau sous l'église"),
    ("CORBEAU", "Oiseau noir de mauvais augure"), ("TOMBE", "On y repose pour l'éternité"),
    ("CHAUDRON", "On y fait bouillir les potions"), ("GRIMOIRE", "Le livre des sortilèges"),
    ("CERCUEIL", "La boîte du vampire"), ("ARAIGNEE", "Elle tisse sa toile"), ("SQUELETTE", "Que des os"),
    ("CITROUILLE", "On la creuse le 31 octobre"), ("BALAI", "Le véhicule de la sorcière"), ("HIBOU", "Il hulule la nuit"),
    ("LOUPGAROU", "Il hurle à la pleine lune"), ("POTION", "Breuvage magique"), ("BONBON", "Le butin d'Halloween"),
    ("SORTILEGE", "Une formule magique"), ("CHANDELLE", "Elle éclaire la crypte"), ("MALEFICE", "Un mauvais sort"),
    ("GARGOUILLE", "Statue grimaçante des cathédrales"), ("REVENANT", "Un esprit qui revient hanter"),
    ("DEMON", "Créature des enfers"), ("FAUCHEUSE", "Elle porte une grande faux"), ("BROUILLARD", "Brume épaisse"),
    ("CIMETIERE", "Le jardin des tombes"), ("LANTERNE", "Elle éclaire le chemin"), ("MASQUE", "Il cache le visage"),
    ("SPECTRE", "Apparition fantomatique"), ("MINUIT", "L'heure du crime"),
]
REWARDS = [450, 340, 250, 180, 130, 90]  # by number of tries used
GIF_NAME, PNG_NAME = "motus.gif", "motus.png"


def score(guess: str, word: str) -> list[tuple[str, str]]:
    """Motus colours: good place, wrong place (each letter counted once) or absent."""
    out = [(g, "miss") for g in guess]
    left = {}
    for i, (g, w) in enumerate(zip(guess, word)):
        if g == w:
            out[i] = (g, "good")
        else:
            left[w] = left.get(w, 0) + 1
    for i, g in enumerate(guess):
        if out[i][1] != "good" and left.get(g, 0) > 0:
            out[i] = (g, "near")
            left[g] -= 1
    return out


def normalize(text: str) -> str:
    return "".join(c for c in strip_accents(text).upper() if c.isalpha())


class GuessModal(discord.ui.Modal, title="Ta proposition"):
    def __init__(self, view: "MotusView"):
        super().__init__()
        self.view = view
        n = len(view.word)
        self.guess = discord.ui.TextInput(label=f"Un mot de {n} lettres qui commence par {view.word[0]}",
                                          placeholder=view.word[0] + "…", min_length=n, max_length=n + 4)
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        await self.view.submit(interaction, str(self.guess.value))


class MotusView(GameView):
    banner_key = "motus"
    kicker = "MOTUS DES OMBRES"
    owner_hint = "Lance ta propre partie avec /motus."

    def __init__(self, bot, interaction, allowed: bool, word=None):
        super().__init__(bot, interaction, timeout=600)
        self.state = "play" if allowed else "empty"
        self.word, self.hint = word or random.choice(WORDS)
        self.rows: list[list[tuple[str, str]]] = []
        self.flash = ""
        self.reward = None
        self.animating = False
        self.anim = 0
        if allowed:
            self.banner_key = None  # the letter grid replaces the banner

    def build(self) -> Panel:
        p = Panel("cyan")
        if self.state == "empty":
            p.banner(self.banner_key)
            p.title("Les ombres se taisent", icon="book",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        p.image(GIF_NAME if self.animating else PNG_NAME)
        n, tries = len(self.word), len(self.rows)
        if self.state == "play":
            body = (f"Trouve le mot de **{n} lettres** qui commence par **{self.word[0]}** en {art.TRIES} essais.\n"
                    f"{E.check} vert : bien placée · {E.question} cercle orange : mal placée")
            if tries >= 3:
                body += f"\n{E.crystal} *Indice : {self.hint}*"
            if self.flash:
                body = self.flash + "\n" + body
            p.title(f"Essai {tries + 1}/{art.TRIES}", icon="book", body=body)
            p.row(button("Proposer un mot", "scroll", "success", self._ask),
                  button("Abandonner", "cross", "danger", self._give_up))
        else:
            won = self.state == "won"
            p.title("Mot trouvé !" if won else "Les ombres gardent leur secret…", icon="sparkle" if won else "skull",
                    body=(f"Trouvé en **{tries}** essai{'s' if tries > 1 else ''} !\n" if won else
                          f"Le mot était **{self.word}** — *{self.hint}*.\n") + self.reward.line())
            left = self.store.remaining(self.guild_id, self.owner_id, "motus")
            p.row(nav("motus", self.owner_id, f"Nouveau mot ({left})", "book", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def extra_files(self):
        if self.state == "empty":
            return []
        data = await asyncio.to_thread(art.grid_png, self.rows, len(self.word), self.word[0])
        return [image_file(data, PNG_NAME)]

    async def _ask(self, interaction):
        if self.state != "play":
            return await interaction.response.defer()
        await interaction.response.send_modal(GuessModal(self))

    async def submit(self, interaction, text: str):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            guess = normalize(text)
            if len(guess) != len(self.word) or guess[0] != self.word[0]:
                self.flash = (f"{E.cross} « {text[:30]} » : il faut un mot de **{len(self.word)} lettres** "
                              f"commençant par **{self.word[0]}**.")
                return await self.refresh(interaction)
            self.flash = ""
            self.rows.append(score(guess, self.word))
            if guess == self.word:
                self._end(True)
            elif len(self.rows) >= art.TRIES:
                self._end(False)
            await interaction.response.defer()
            data, seconds = await asyncio.to_thread(art.flip_gif, self.rows, len(self.word), self.word[0])
            self.animating = True
            self.anim += 1
            anim = self.anim
            await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
            still = await asyncio.to_thread(art.grid_png, self.rows, len(self.word), self.word[0])
        await asyncio.sleep(seconds)
        async with self.lock:
            if self.anim == anim:  # a newer guess replaces this animation
                self.animating = False
                await self.push(attachments=[image_file(still, PNG_NAME)])

    async def _give_up(self, interaction):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            self._end(False)
            await self.refresh(interaction)

    def _end(self, won: bool):
        self.state = "won" if won else "lost"
        tries = len(self.rows)
        self.reward = grant(self.store, self.guild_id, self.owner_id, REWARDS[tries - 1] if won else 0,
                            20 if won else 4, "motus", stats={"motus_win": 1} if won else None)
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self._end(False)


class Motus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["motus"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "motus")
        await MotusView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="motus", description="🔤 Motus des ombres : trouve le mot d'Halloween en 6 essais")
    @app_commands.guild_only()
    async def motus(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Motus(bot))
