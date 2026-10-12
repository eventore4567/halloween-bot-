"""/quiz — « Le Grand Frisson », a haunted TV quiz show.

12 questions of growing difficulty on a money ladder with two safe rungs,
three lifelines (50/50, the ghost's whisper, the audience) and "who hides
in the shadows?" video rounds. Every question is an animated GIF with its
own countdown, like a short clip of the show.
"""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import show
from ..content import quiz_bank
from ..content.games import SHADOWS
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

LETTERS = "ABCD"
GIF_NAME, PNG_NAME = "frisson.gif", "frisson.png"
GHOST_ACCURACY = {1: 0.95, 2: 0.85, 3: 0.75, 4: 0.65, 5: 0.55}
PUBLIC_RIGHT = {1: 72, 2: 60, 3: 50, 4: 42, 5: 34}


def audience_poll(correct: int, removed: set, level: int, rnd=random) -> dict[int, int]:
    """Percentages for each visible answer; the right one is usually (not always) ahead."""
    alive = [i for i in range(4) if i not in removed]
    weights = {i: rnd.uniform(5, 30) for i in alive}
    weights[correct] = PUBLIC_RIGHT[level] + rnd.uniform(-12, 12)
    total = sum(weights.values())
    poll = {i: round(100 * w / total) for i, w in weights.items()}
    poll[max(poll, key=poll.get)] += 100 - sum(poll.values())
    return poll


def ghost_hint(correct: int, removed: set, level: int, rnd=random) -> int:
    if rnd.random() < GHOST_ACCURACY[level]:
        return correct
    return rnd.choice([i for i in range(4) if i not in removed and i != correct])


class ShowView(GameView):
    banner_key = "quiz"
    kicker = "LE GRAND FRISSON"
    owner_hint = "Lance ta propre émission avec /quiz."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=900)
        self.state = "intro"
        self.correct_count = 0
        self.lifelines = {"fifty": True, "ghost": True, "public": True}
        self.shadow = None  # emoji key of the hidden creature in video rounds
        self.text = ""
        self.category = ""
        self.options: list[str] = []
        self.correct = 0
        self.removed: set[int] = set()
        self.picked: int | None = None
        self.hint = ""
        self.deadline = 0.0
        self.token = 0
        self.timer: asyncio.Task | None = None
        self.result = ""
        self.final = None
        self.image = None

    def banner_fmt(self):
        return {"questions": quiz_bank.TOTAL}

    # ------------------------------------------------------------- helpers
    @property
    def level(self) -> int:
        return config.SHOW_LEVELS[min(self.correct_count, len(config.SHOW_LEVELS) - 1)]

    @property
    def value(self) -> int:
        return config.SHOW_LADDER[min(self.correct_count, len(config.SHOW_LADDER) - 1)]

    @property
    def banked(self) -> int:
        return config.SHOW_LADDER[self.correct_count - 1] if self.correct_count else 0

    def _ladder_line(self):
        cells = []
        for i, v in enumerate(config.SHOW_LADDER):
            txt = config.short(v)
            if i < self.correct_count:
                cells.append(f"~~{txt}~~")
            elif i == self.correct_count and self.state in ("question", "answer"):
                cells.append(f"**[{txt}]**")
            elif (i + 1) in config.SHOW_SAFE:
                cells.append(f"__{txt}__")
            else:
                cells.append(txt)
        return " › ".join(cells)

    # -------------------------------------------------------------- render
    def build(self) -> Panel:
        p = Panel("purple")
        if self.state in ("question", "answer", "end") and self.image:
            p.image(self.image)
        else:
            p.banner(self.banner_key)
        getattr(self, f"_build_{self.state}")(p)
        p.footer(self.footer())
        return p

    def _build_empty(self, p: Panel):
        p.title("Le plateau est fermé pour ce soir", icon="hourglass",
                body=f"Tu as joué tes émissions. Le studio rouvre {relative(config.next_midnight_ts())}.\n"
                     f"{E.scroll} Un **ticket du Grand Frisson** (boutique) ou un {E.potion_blue} **Élixir du savoir** "
                     f"(La Formule) t'offre une émission de plus.")
        p.row(nav("shop", self.owner_id, "Boutique", "witch", "primary"),
              nav("hub", self.owner_id, "Autres jeux", "pumpkin"))

    def _build_intro(self, p: Panel):
        left = self.store.remaining(self.guild_id, self.owner_id, "quiz")
        safe = " et ".join(f"**{config.SHOW_LADDER[r - 1]}**" for r in sorted(config.SHOW_SAFE))
        p.title("Bienvenue sur le plateau !", icon="skull",
                body=f"Ce soir, **12 questions** te séparent de **{config.fmt(config.SHOW_LADDER[-1])}** {E.candy}. "
                     f"Chaque bonne réponse te fait grimper, tu peux **encaisser** quand tu veux. Une erreur et tu "
                     f"redescends au dernier palier atteint ({safe}).")
        p.sep()
        p.text(f"{E.joker} **50/50** · {E.ghost} **Murmure du fantôme** · {E.crystal} **Vote du public** — "
               f"un de chaque par émission\n"
               f"{E.eye} Questions **3, 6 et 9** : manche vidéo *« Qui se cache dans l'ombre ? »*\n"
               f"{E.shield} Un **bouclier** dans ton sac efface automatiquement une erreur.\n"
               f"-# {quiz_bank.TOTAL} questions en réserve, jamais deux fois la même tant qu'il en reste.")
        p.text(f"-# {self._ladder_line()}")
        p.sep()
        p.row(button(f"Lancer l'émission ({left} ce soir)", "lightning", "success", self._start, disabled=left <= 0),
              nav("trophies", self.owner_id, "Succès", "medal1"))

    def _build_question(self, p: Panel):
        n = self.correct_count + 1
        body = (f"### {self.text}" if not self.shadow else
                "### Qui se cache dans l'ombre ?\n-# La silhouette s'illumine à mi-temps… mais réponds avant la fin !")
        body += f"\n{E.hourglass} Fin du chrono {relative(self.deadline)}"
        if self.hint:
            body += f"\n{self.hint}"
        p.title(f"Question {n} · pour {config.fmt(self.value)} {E.candy}", icon="eye" if self.shadow else "crystal",
                body=body)
        btns = [button(f"{LETTERS[i]} · {opt}"[:80], None, "secondary", self._answer(i), disabled=i in self.removed)
                for i, opt in enumerate(self.options)]
        p.row(*btns[:2])
        p.row(*btns[2:])
        jokers = self.store.item_qty(self.guild_id, self.owner_id, "joker")
        fifty_ok = bool(self.lifelines["fifty"] or jokers) and not self.removed
        p.row(button("50/50" + ("" if self.lifelines["fifty"] else f" ({jokers})"), "joker", "primary", self._fifty,
                     disabled=not fifty_ok),
              button("Fantôme", "ghost", "primary", self._ghost, disabled=not self.lifelines["ghost"]),
              button("Public", "crystal", "primary", self._public, disabled=not self.lifelines["public"]),
              button(f"Encaisser {config.fmt(self.banked)}", "candy_bag", "success", self._cash,
                     disabled=self.correct_count == 0))
        p.text(f"-# {self._ladder_line()}")

    def _build_answer(self, p: Panel):
        head, _, rest = self.result.partition("\n")
        p.title(head, icon="check" if self.picked == self.correct else "shield", body=rest)
        p.row(button(f"Question {self.correct_count + 1} pour {config.fmt(self.value)}", "lightning", "success",
                     self._next),
              button(f"Encaisser {config.fmt(self.banked)}", "candy_bag", "primary", self._cash))
        p.text(f"-# {self._ladder_line()}")

    def _build_end(self, p: Panel):
        title, icon = {"top": ("LE GRAND FRISSON EST À TOI !", "crown"),
                       "cash": ("Tu repars avec le magot !", "candy_bag"),
                       "fall": ("Fin de l'émission…", "skull")}[self.final["how"]]
        line = self.final["reward"].line()
        p.title(title, icon=icon, body=self.result + ("\n\n" + line if line else ""))
        left = self.store.remaining(self.guild_id, self.owner_id, "quiz")
        p.row(nav("quiz", self.owner_id, f"Nouvelle émission ({left})", "lightning", "success"),
              nav("top", self.owner_id, "Classement", "trophy"), nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))

    # ------------------------------------------------------------- actions
    async def _start(self, interaction):
        async with self.lock:
            if self.state != "intro":
                return await interaction.response.defer()
            if not self.store.use_play(self.guild_id, self.owner_id, "quiz"):
                self.state = "empty"
                return await self.refresh(interaction)
            await interaction.response.defer()
            self.store.stat_add(self.guild_id, self.owner_id, "shows")
            await self._ask(interaction)

    def _prepare(self):
        g, u = self.guild_id, self.owner_id
        self.removed, self.picked, self.hint = set(), None, ""
        if self.correct_count + 1 in config.SHOW_SHADOW_RUNGS:
            choices = random.sample(SHADOWS, 4)
            self.shadow = choices[0][0]
            self.options = [name for _, name in choices]
            random.shuffle(self.options)
            self.correct = self.options.index(choices[0][1])
            self.text, self.category = "Qui se cache dans l'ombre ?", "Manche vidéo"
            return
        self.shadow = None
        q, reset = quiz_bank.pick(self.level, self.store.quiz_seen(g, u))
        if reset:
            self.store.forget_seen(g, u, [x.qid for x in quiz_bank.BY_LEVEL[self.level]])
        self.store.mark_seen(g, u, q.qid)
        self.text, self.category = q.text, q.category
        self.options, self.correct = q.shuffled()

    async def _render_question(self, seconds: int):
        data = await asyncio.to_thread(
            show.question_gif, self.text, self.category, self.options, self.correct_count, config.SHOW_LADDER,
            config.SHOW_SAFE, seconds, tuple(sorted(self.removed)), self.shadow)
        self.image = GIF_NAME
        return image_file(data, GIF_NAME)

    async def _ask(self, interaction):
        self._prepare()
        seconds = config.QUIZ_LEVELS[self.level]["time"] + (6 if self.shadow else 0)
        file = await self._render_question(seconds)
        self.deadline = time.time() + seconds + 1
        self.state = "question"
        self.token += 1
        await self.refresh(interaction, attachments=[file])
        self._arm(self.token, seconds + 1.5)

    def _arm(self, token, delay):
        if self.timer and not self.timer.done():
            self.timer.cancel()

        async def expire():
            await asyncio.sleep(delay)
            async with self.lock:
                if self.state == "question" and self.token == token:
                    file = await self._resolve(None)
                    await self.push(attachments=[file] if file else None)
        self.timer = asyncio.create_task(expire())

    def _answer(self, index):
        async def cb(interaction):
            async with self.lock:
                if self.state != "question":
                    return await interaction.response.defer()
                await interaction.response.defer()
                file = await self._resolve(index if time.time() <= self.deadline else None)
                await self.refresh(interaction, attachments=[file] if file else None)
        return cb

    async def _resolve(self, index):
        g, u = self.guild_id, self.owner_id
        self.picked = index
        self.token += 1
        if self.timer and not self.timer.done() and asyncio.current_task() is not self.timer:
            self.timer.cancel()
        right = self.options[self.correct]
        info = config.QUIZ_LEVELS[self.level]
        if index == self.correct:
            self.correct_count += 1
            r = grant(self.store, g, u, 0, info["xp"], "quiz", stats={"quiz_right": 1},
                      best={"quiz_best_streak": self.correct_count})
            if self.correct_count >= len(config.SHOW_LADDER):
                self.result = f"{E.check} **{right}** — et c'est la dernière marche !"
                return await self._finish("top", config.SHOW_LADDER[-1], "MAÎTRE DU GRAND FRISSON !")
            self.result = (f"Bonne réponse !\n{E.check} **{right}** · tu as **{config.fmt(self.banked)}** {E.candy} "
                           f"en poche" + (f"\n{r.line()}" if r.achievements or r.leveled else ""))
            self.state = "answer"
            safe = self.correct_count in config.SHOW_SAFE
            return await self._reveal(f"PALIER ATTEINT · {config.fmt(self.banked)} GARANTIS" if safe else "BONNE RÉPONSE !")
        grant(self.store, g, u, 0, 2, "quiz", stats={"quiz_wrong": 1})
        what = "Temps écoulé !" if index is None else f"Raté : c'était **{right}**."
        if self.store.use_item(g, u, "shield"):
            self.result = (f"Sauvé par ton bouclier !\n{E.cross} {what}\n{E.shield} Ton bouclier se brise mais tu "
                           f"restes en jeu à **{config.fmt(self.banked)}** {E.candy}.")
            self.state = "answer"
            return await self._reveal("BOUCLIER BRISÉ · TU RESTES EN JEU")
        kept = config.show_safe_amount(self.correct_count)
        self.result = f"{E.cross} {what} Tu redescends au palier : **{config.fmt(kept)}** {E.candy}."
        return await self._finish("fall", kept, f"RATÉ · TU REPARS AVEC {config.fmt(kept)}")

    async def _reveal(self, banner):
        played = self.correct_count - 1 if self.picked == self.correct else self.correct_count
        played = max(0, min(played, len(config.SHOW_LADDER) - 1))
        data = await asyncio.to_thread(
            show.reveal_png, self.text, self.category, self.options, played, config.SHOW_LADDER, config.SHOW_SAFE,
            self.correct, self.picked, tuple(sorted(self.removed)), self.shadow, banner)
        self.image = PNG_NAME
        return image_file(data, PNG_NAME)

    async def _finish(self, how, amount, banner):
        stats = {"show_top": 1} if how == "top" else None
        reward = grant(self.store, self.guild_id, self.owner_id, amount, 10 + 4 * self.correct_count,
                       "grand-frisson", stats=stats, best={"show_best": self.correct_count})
        self.final = dict(how=how, amount=amount, reward=reward)
        self.state = "end"
        file = await self._reveal(banner) if banner else None
        self.finish()
        return file

    async def _next(self, interaction):
        async with self.lock:
            if self.state != "answer":
                return await interaction.response.defer()
            await interaction.response.defer()
            await self._ask(interaction)

    async def _cash(self, interaction):
        async with self.lock:
            if self.state not in ("question", "answer") or self.correct_count == 0:
                return await interaction.response.defer()
            self.token += 1
            if self.timer and not self.timer.done():
                self.timer.cancel()
            self.result = f"{E.candy_bag} Tu encaisses après **{self.correct_count}** bonne(s) réponse(s)."
            await self._finish("cash", self.banked, "")
            await self.refresh(interaction)

    async def _fifty(self, interaction):
        async with self.lock:
            if self.state != "question" or self.removed:
                return await interaction.response.defer()
            if self.lifelines["fifty"]:
                self.lifelines["fifty"] = False
            elif not self.store.use_item(self.guild_id, self.owner_id, "joker"):
                return await interaction.response.defer()
            await interaction.response.defer()
            wrong = [i for i in range(4) if i != self.correct]
            self.removed = set(random.sample(wrong, 2))
            seconds = max(1, int(self.deadline - time.time()))
            file = await self._render_question(seconds)
            await self.refresh(interaction, attachments=[file])

    async def _ghost(self, interaction):
        async with self.lock:
            if self.state != "question" or not self.lifelines["ghost"]:
                return await interaction.response.defer()
            self.lifelines["ghost"] = False
            pick = ghost_hint(self.correct, self.removed, self.level)
            self.hint = f"{E.ghost} *Le fantôme murmure : « Je crois que c'est **{LETTERS[pick]}**… »*"
            await self.refresh(interaction)

    async def _public(self, interaction):
        async with self.lock:
            if self.state != "question" or not self.lifelines["public"]:
                return await interaction.response.defer()
            self.lifelines["public"] = False
            poll = audience_poll(self.correct, self.removed, self.level)
            lines = [f"`{LETTERS[i]}` {E.bar(pct, 100, 6)} **{pct} %**" for i, pct in sorted(poll.items())]
            self.hint = f"{E.crystal} **Le public a voté :**\n" + "\n".join(lines)
            await self.refresh(interaction)

    def on_expire(self):
        if self.timer and not self.timer.done():
            self.timer.cancel()


class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["quiz"] = self.open

    async def open(self, interaction, edit=False):
        view = ShowView(self.bot, interaction)
        if self.bot.store.remaining(interaction.guild_id, interaction.user.id, "quiz") <= 0:
            view.state = "empty"
        await view.start(interaction, edit)

    @app_commands.command(name="quiz",
                          description="📺 Le Grand Frisson : le jeu télé d'Halloween, 12 questions jusqu'à 1 500 bonbons")
    @app_commands.guild_only()
    async def quiz(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Quiz(bot))
