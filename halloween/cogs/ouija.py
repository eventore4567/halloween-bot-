"""/ouija — the spirits spell a word on an animated board; find which one."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import ouija as board
from ..content.games import strip_accents
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

# (words, hold per letter in ms, candies, how the spirit spells)
ROUNDS = [
    (["Ombre", "Crâne", "Balai", "Tombe", "Hibou", "Lune", "Momie", "Chat", "Cape", "Brume", "Crypte", "Démon",
      "Orage", "Masque"], 650, 40, "normal"),
    (["Fantôme", "Vampire", "Sorcière", "Chaudron", "Squelette", "Araignée", "Cimetière", "Chauve-souris",
      "Loup-garou", "Cercueil", "Potion", "Gargouille", "Revenant", "Chandelle"], 470, 70, "normal"),
    (["Citrouille", "Malédiction", "Épouvantail", "Nécromancien", "Ensorcelé", "Frankenstein", "Envoûtement",
      "Sortilège", "Possession", "Banshee", "Catacombes", "Exorciste", "Poltergeist", "Halloween"], 520, 120,
     "reverse"),
]
PERFECT_BONUS = 60
GIF_NAME, PNG_NAME = "ouija.gif", "ouija.png"


def spelled(word: str) -> str:
    return board.letters_of(strip_accents(word))


def pick_round(index: int, rnd=random) -> tuple[str, list[str]]:
    """The hidden word and four shuffled choices (decoys of a similar length)."""
    words = ROUNDS[index][0]
    answer = rnd.choice(words)
    others = sorted((w for w in words if spelled(w) != spelled(answer)),
                    key=lambda w: (abs(len(spelled(w)) - len(spelled(answer))), rnd.random()))
    choices = [answer] + others[:3]
    rnd.shuffle(choices)
    return answer, choices


def ouija_reward(correct: int) -> int:
    return sum(r[2] for r in ROUNDS[:correct]) + (PERFECT_BONUS if correct == len(ROUNDS) else 0)


class OuijaView(GameView):
    banner_key = "ouija"
    kicker = "LA PLANCHE OUIJA"
    owner_hint = "Fais parler ta propre planche avec /ouija."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=300)
        self.state = "ready" if allowed else "empty"
        self.round = 0
        self.correct = 0
        self.answer = ""
        self.choices: list[str] = []
        self.flash = ""
        self.reward = None
        self.seed = random.randrange(1000)
        self.token = 0
        self._still = b""

    def build(self) -> Panel:
        p = Panel("purple")
        if self.state in ("ready", "empty"):
            p.banner(self.banner_key)
        else:
            p.image(GIF_NAME if self.state == "spell" else PNG_NAME)
        if self.state == "empty":
            p.title("Les esprits se taisent", icon="candle",
                    body=f"Plus de séances aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        mode = ROUNDS[min(self.round, len(ROUNDS)) - 1][3] if self.round else "normal"
        if self.state == "ready":
            p.title("La Planche Ouija", icon="crystal",
                    body="Pose ton doigt sur la planchette… Un esprit va **épeler un mot**, lettre par lettre.\n"
                         "Suis bien la loupe : elle ne repassera pas ! Ensuite, choisis le bon mot.\n"
                         f"{E.ghost} 3 manches de plus en plus rapides · {E.skull} la dernière est épelée **à l'envers**\n"
                         f"-# Une erreur et l'esprit s'en va · {config.fmt(ouija_reward(len(ROUNDS)))} bonbons pour une séance parfaite")
            p.row(button("Allumer les bougies", "candle", "success", self._start))
        elif self.state == "spell":
            how = "**à l'envers** " if mode == "reverse" else ""
            p.title(f"Manche {self.round}/{len(ROUNDS)} · l'esprit épelle {how}…", icon="eye",
                    body=(self.flash + "\n" if self.flash else "") + f"{E.crystal} *Ne quitte pas la loupe des yeux…*")
        elif self.state == "answer":
            ask = "Quel mot l'esprit a-t-il épelé **à l'envers** ?" if mode == "reverse" else "Quel mot l'esprit a-t-il épelé ?"
            p.title(f"Manche {self.round}/{len(ROUNDS)} · ta réponse", icon="question", body=ask)
            p.row(*[button(w, None, "primary", self._guess(w)) for w in self.choices])
        else:
            won = self.correct == len(ROUNDS)
            p.title("Séance parfaite !" if won else "L'esprit s'en est allé…", icon="sparkle" if won else "skull",
                    body=(self.flash + "\n" if self.flash else "")
                    + f"Mots trouvés : **{self.correct}/{len(ROUNDS)}**\n{self.reward.line()}")
            left = self.store.remaining(self.guild_id, self.owner_id, "ouija")
            p.row(nav("ouija", self.owner_id, f"Nouvelle séance ({left})", "crystal", "success"),
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
        _words, hold, _candies, mode = ROUNDS[self.round - 1]
        self.answer, self.choices = pick_round(self.round - 1)
        letters = spelled(self.answer)
        if mode == "reverse":
            letters = letters[::-1]
        self.seed += 1
        data, seconds = await asyncio.to_thread(board.spell_gif, letters, hold, self.seed)
        still = await asyncio.to_thread(board.board_png, self.seed)
        self._still = still
        self.state = "spell"
        self.token += 1
        await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
        self._arm(seconds + 0.8, self.token)

    def _arm(self, delay: float, token: int):
        async def reveal():
            await asyncio.sleep(delay)
            await self._reveal(token)
        asyncio.create_task(reveal())

    async def _reveal(self, token: int):
        async with self.lock:
            if self.state == "spell" and self.token == token:
                self.state = "answer"
                await self.push(attachments=[image_file(self._still, PNG_NAME)])

    def _guess(self, word: str):
        async def cb(interaction):
            async with self.lock:
                if self.state != "answer":
                    return await interaction.response.defer()
                if spelled(word) == spelled(self.answer):
                    self.correct += 1
                    self.flash = f"{E.check} Oui… c'était bien **{self.answer}**."
                    if self.round < len(ROUNDS):
                        await interaction.response.defer()
                        return await self._next_round(interaction)
                else:
                    self.flash = f"{E.cross} Non ! L'esprit épelait **{self.answer}**."
                self._end()
                await self.refresh(interaction)
        return cb

    def _end(self):
        self.state = "end"
        self.reward = grant(self.store, self.guild_id, self.owner_id, ouija_reward(self.correct), 5 + 5 * self.correct,
                            "ouija", stats={"ouija_words": self.correct},
                            best={"ouija_best": self.correct})
        self.finish()

    def on_expire(self):
        if self.state in ("spell", "answer"):
            self._end()


class Ouija(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["ouija"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "ouija")
        await OuijaView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="ouija", description="🔮 La Planche Ouija : l'esprit épelle un mot, devine lequel")
    @app_commands.guild_only()
    async def ouija(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Ouija(bot))
