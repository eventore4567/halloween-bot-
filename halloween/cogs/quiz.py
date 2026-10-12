"""/quiz — 5 difficulty levels, live countdown, combos, jokers and shields."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content import quiz_bank
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, nav, relative

LETTERS = "ABCD"


def combo_multiplier(streak: int) -> float:
    """+10 % per correct answer in a row, up to ×2."""
    return 1 + 0.1 * min(max(streak - 1, 0), 10)


def compute_gain(level: int, streak: int, elapsed: float, rnd=random) -> tuple[int, bool]:
    info = config.QUIZ_LEVELS[level]
    base = rnd.randint(*info["reward"])
    fast = elapsed <= info["time"] / 3
    gain = base * combo_multiplier(streak) * (1.2 if fast else 1.0)
    return int(round(gain)), fast


class QuizView(GameView):
    banner_key = "quiz"
    owner_hint = "Lance ton propre quiz avec /quiz."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=900)
        self.state = "menu"
        self.level = 1
        self.question: quiz_bank.Question | None = None
        self.options: list[str] = []
        self.correct = 0
        self.removed: set[int] = set()
        self.picked: int | None = None
        self.deadline = 0.0
        self.asked_at = 0.0
        self.streak = 0
        self.best = 0
        self.session_gain = 0
        self.number = 0
        self.last = None  # dict describing the last answer
        self.timer: asyncio.Task | None = None
        self.token = 0

    def banner_fmt(self):
        return {"questions": quiz_bank.TOTAL}

    # ------------------------------------------------------------------ render
    def build(self) -> Panel:
        color = {"menu": "orange", "question": "purple", "answer": "green" if self.last and self.last["ok"] else "red",
                 "empty": "red"}[self.state]
        p = Panel(color).banner(self.banner_key)
        getattr(self, f"_build_{self.state}")(p)
        return p

    def _status_line(self):
        g, u = self.guild_id, self.owner_id
        items = self.store.items(g, u)
        left = self.store.remaining(g, u, "quiz")
        bits = [f"{E.hourglass} Questions restantes aujourd'hui : **{left}/{self.store.limit_for(g, u, 'quiz')}**"]
        extra = []
        if items.get("joker"):
            extra.append(f"{E.joker} ×{items['joker']}")
        if items.get("shield"):
            extra.append(f"{E.shield} ×{items['shield']}")
        if extra:
            bits.append(" · ".join(extra))
        return " · ".join(bits)

    def _build_menu(self, p: Panel):
        p.title("Choisis ton niveau… si tu oses !", icon="crystal",
                body=f"Plus c'est dur, plus ça rapporte de {E.candy}. Enchaîne les bonnes réponses pour un "
                     f"**combo jusqu'à ×2**, réponds vite pour **+20 %**.")
        p.sep()
        lines = []
        for lvl, info in config.QUIZ_LEVELS.items():
            lo, hi = info["reward"]
            lines.append(f"{E(info['emoji'])} **{info['name']}** — {lo} à {hi} {E.candy}\n"
                         f"-# Difficulté {E.bar(lvl, 5, 5)} · {len(quiz_bank.BY_LEVEL.get(lvl, []))} questions · "
                         f"{info['time']} s")
        p.text("\n".join(lines))
        p.sep()
        p.text(self._status_line())
        btns = []
        for lvl, info in config.QUIZ_LEVELS.items():
            btns.append(button(info["name"], info["emoji"], info["style"], self._choose(lvl)))
        p.row(*btns)
        p.footer(self.footer("Seul toi peux jouer à ce quiz"))

    def _question_block(self, p: Panel):
        q = self.question
        info = config.QUIZ_LEVELS[self.level]
        p.title(f"Question {self.number} · {info['name']}", icon=info["emoji"],
                body=f"-# {q.category}" + (f" · {E.fire} Série de **{self.streak}** (×{combo_multiplier(self.streak + 1):.1f})"
                                          if self.streak else ""))
        p.text(f"### {q.text}")

    def _build_question(self, p: Panel):
        self._question_block(p)
        p.text(f"{E.hourglass} Réponds {relative(self.deadline)}")
        rows = []
        for i, opt in enumerate(self.options):
            disabled = i in self.removed
            rows.append(button(f"{LETTERS[i]} · {opt}"[:80], None, "secondary", self._answer(i), disabled=disabled))
        p.row(*rows[:2])
        p.row(*rows[2:])
        items = self.store.items(self.guild_id, self.owner_id)
        tools = []
        if items.get("joker") and not self.removed:
            tools.append(button(f"Joker 50/50 (×{items['joker']})", "joker", "primary", self._joker))
        tools.append(button("Abandonner", "cross", "danger", self._quit))
        p.row(*tools)
        p.footer(self.footer(self._status_line().split(" · ")[0].replace("Questions restantes aujourd'hui", "Restantes")))

    def _build_answer(self, p: Panel):
        self._question_block(p)
        last = self.last
        lines = []
        for i, opt in enumerate(self.options):
            if i == self.correct:
                lines.append(f"{E.check} **{opt}**")
            elif i == self.picked:
                lines.append(f"{E.cross} ~~{opt}~~")
            elif i in self.removed:
                continue
            else:
                lines.append(f"{E.bar_m0} {opt}")
        p.text("\n".join(lines))
        p.sep()
        if last["ok"]:
            head = f"## {E.sparkle} Bonne réponse !"
            detail = [last["reward"].line()]
            extras = []
            if last["fast"]:
                extras.append(f"{E.lightning} Rapide **+20 %**")
            if self.streak > 1:
                extras.append(f"{E.fire} Combo **×{combo_multiplier(self.streak):.1f}**")
            if extras:
                detail.append(" · ".join(extras))
        else:
            head = f"## {E.skull} {'Temps écoulé !' if last.get('timeout') else 'Raté !'}"
            detail = [f"La bonne réponse était **{self.options[self.correct]}**."]
            if last.get("shielded"):
                detail.append(f"{E.shield} Ton bouclier a protégé ta série de **{self.streak}** !")
            elif last.get("lost_streak"):
                detail.append(f"{E.fire} Série perdue ({last['lost_streak']}).")
            detail.append(last["reward"].line())
        p.text(head + "\n" + "\n".join(d for d in detail if d))
        p.text(f"-# Session : **+{config.fmt(self.session_gain)}** {E.candy} · meilleure série **{self.best}**")
        p.sep()
        p.text(self._status_line())
        left = self.store.remaining(self.guild_id, self.owner_id, "quiz")
        info = config.QUIZ_LEVELS[self.level]
        p.row(button("Question suivante", info["emoji"], "success", self._next, disabled=left <= 0),
              button("Changer de niveau", "crystal", "secondary", self._menu),
              nav("profile", self.owner_id, "Profil", "pumpkin_lit"))
        p.footer(self.footer())

    def _build_empty(self, p: Panel):
        p.title("Plus de questions pour aujourd'hui !", icon="hourglass",
                body=f"Ta boule de cristal est épuisée. Elle se recharge {relative(config.next_midnight_ts())}.\n\n"
                     f"{E.potion_blue} Trouve l'**Élixir du savoir** au chaudron ou achète un "
                     f"{E.scroll} **Parchemin du savoir** à la boutique : **+5 questions**.")
        if self.session_gain:
            p.text(f"-# Session : **+{config.fmt(self.session_gain)}** {E.candy} · meilleure série **{self.best}**")
        p.sep()
        o = self.owner_id
        p.row(nav("cauldron", o, "Chaudron", "cauldron", "success"), nav("shop", o, "Boutique", "witch", "primary"),
              nav("hub", o, "Autres jeux", "pumpkin"))
        p.footer(self.footer())

    # ----------------------------------------------------------------- actions
    def _choose(self, level):
        async def cb(interaction):
            self.level = level
            await self._ask(interaction)
        return cb

    async def _ask(self, interaction):
        g, u = self.guild_id, self.owner_id
        if not self.store.use_play(g, u, "quiz"):
            self.state = "empty"
            return await self.refresh(interaction)
        seen = self.store.quiz_seen(g, u)
        q, reset = quiz_bank.pick(self.level, seen)
        if reset:
            self.store.forget_seen(g, u, [x.qid for x in quiz_bank.BY_LEVEL[self.level]])
        self.store.mark_seen(g, u, q.qid)
        self.question = q
        self.options, self.correct = q.shuffled()
        self.removed = set()
        self.picked = None
        self.number += 1
        info = config.QUIZ_LEVELS[self.level]
        self.asked_at = time.time()
        self.deadline = self.asked_at + info["time"] + 1
        self.state = "question"
        self.token += 1
        await self.refresh(interaction)
        self._arm_timer(self.token, info["time"] + 1.5)

    def _arm_timer(self, token, delay):
        if self.timer and not self.timer.done():
            self.timer.cancel()

        async def expire():
            await asyncio.sleep(delay)
            async with self.lock:
                if self.state == "question" and self.token == token:
                    self._resolve(None, timeout=True)
                    await self.push()
        self.timer = asyncio.create_task(expire())

    def _answer(self, index):
        async def cb(interaction):
            async with self.lock:
                if self.state != "question":
                    return await interaction.response.defer()
                if time.time() > self.deadline:
                    self._resolve(None, timeout=True)
                else:
                    self._resolve(index)
                await self.refresh(interaction)
        return cb

    def _resolve(self, index, timeout=False):
        g, u = self.guild_id, self.owner_id
        self.picked = index
        ok = index == self.correct
        elapsed = time.time() - self.asked_at
        last = dict(ok=ok, timeout=timeout, fast=False)
        info = config.QUIZ_LEVELS[self.level]
        self.store.stat_add(g, u, "quiz_total")
        if ok:
            self.streak += 1
            self.best = max(self.best, self.streak)
            gain, fast = compute_gain(self.level, self.streak, elapsed)
            last["fast"] = fast
            last["reward"] = grant(self.store, g, u, gain, info["xp"], "quiz")
            self.session_gain += last["reward"].candies
            self.store.stat_add(g, u, "quiz_right")
            self.store.stat_max(g, u, "quiz_best_streak", self.streak)
        else:
            if self.streak >= 2 and self.store.use_item(g, u, "shield"):
                last["shielded"] = True
            else:
                last["lost_streak"] = self.streak if self.streak >= 2 else 0
                self.streak = 0
            last["reward"] = grant(self.store, g, u, 0, 2, "quiz")
        self.last = last
        self.state = "answer"
        if self.timer and not self.timer.done() and asyncio.current_task() is not self.timer:
            self.timer.cancel()

    async def _joker(self, interaction):
        async with self.lock:
            if self.state != "question" or self.removed:
                return await interaction.response.defer()
            if not self.store.use_item(self.guild_id, self.owner_id, "joker"):
                return await interaction.response.defer()
            wrong = [i for i in range(4) if i != self.correct]
            self.removed = set(random.sample(wrong, 2))
            await self.refresh(interaction)

    async def _next(self, interaction):
        async with self.lock:
            if self.state not in ("answer",):
                return await interaction.response.defer()
            await self._ask(interaction)

    async def _menu(self, interaction):
        self.state = "menu"
        await self.refresh(interaction)

    async def _quit(self, interaction):
        async with self.lock:
            if self.state == "question":
                self._resolve(None, timeout=False)
            await self.refresh(interaction)

    def on_expire(self):
        if self.timer and not self.timer.done():
            self.timer.cancel()


class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["quiz"] = self.open

    async def open(self, interaction, edit=False):
        await QuizView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="quiz", description=f"🔮 Quiz maudit : {quiz_bank.TOTAL} questions, 5 niveaux")
    @app_commands.guild_only()
    async def quiz(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Quiz(bot))
