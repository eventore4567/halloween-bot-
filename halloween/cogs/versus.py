"""/defi — live head-to-head in one panel: quiz race or reflex duel, first to 3 points, candy stake."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art.versus import versus_gif
from ..content import quiz_bank
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, button, image_file, notice, relative, stable_message
from .profile import avatar_bytes

WIN_POINTS = 3
QUESTION_TIME = 20
GIF_NAME = "defi.gif"
MODES = {"quiz": "Quiz éclair", "reflexe": "Réflexes"}
LETTERS = "ABCD"


class VersusView(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int, p1, p2, mode: str, stake: int):
        super().__init__(timeout=None)
        self.bot, self.store, self.guild_id = bot, bot.store, guild_id
        self.p1, self.p2, self.mode, self.stake = p1, p2, mode, stake
        self.state = "invite"
        self.score = {p1.id: 0, p2.id: 0}
        self.round = 0
        self.history: list[str] = []
        self.note = ""
        self.lock = asyncio.Lock()
        self.message = None
        self.deadline = time.time() + 60
        self.token = 0
        self.escrow_key = None
        self.winner = None
        # quiz round
        self.question = None
        self.choices: list[str] = []
        self.locked: set[int] = set()
        self.seen: set[str] = set()
        # reflex round
        self.go_at = 0.0
        self.render()

    # ----------------------------------------------------------------- render
    def render(self):
        self.clear_items()
        p = Panel("red").image(GIF_NAME)
        a, b = self.p1, self.p2
        stake_txt = f"**{config.fmt(self.stake)}** {E.candy}" if self.stake else "l'honneur"
        score = f"{a.mention} **{self.score[a.id]}** — **{self.score[b.id]}** {b.mention}"
        if self.state == "invite":
            p.title(f"Défi {MODES[self.mode]} !", icon="lightning",
                    body=f"{a.mention} défie {b.mention} pour {stake_txt} !\n"
                         f"Premier à **{WIN_POINTS} points**, en direct dans ce panneau. Le gagnant rafle tout.\n"
                         f"{E.hourglass} {b.mention}, accepte {relative(self.deadline)}")
            p.row(button("Relever le défi", "check", "success", self._accept),
                  button("Refuser", "cross", "danger", self._decline))
        elif self.state in ("declined", "expired"):
            p.title("Défi refusé" if self.state == "declined" else "Le défi a expiré", icon="cross",
                    body=f"{b.mention} n'a pas relevé le défi de {a.mention}.")
        else:
            body = score + f" · mise : {stake_txt}"
            if self.history:
                body += "\n" + "\n".join(self.history[-3:])
            if self.note:
                body += "\n" + self.note
            if self.state == "question":
                p.title(f"Question {self.round}", icon="question", body=body)
                q = self.question
                p.text(f"### {q.text}\n" + "\n".join(f"`{LETTERS[i]}` {c}" for i, c in enumerate(self.choices))
                       + f"\n-# Le premier qui trouve marque · une erreur et tu es bloqué pour cette question · "
                         f"fin {relative(self.deadline)}")
                p.row(*[button(LETTERS[i], None, "primary", self._answer(i)) for i in range(len(self.choices))])
            elif self.state == "wait":
                p.title(f"Manche {self.round} · attendez…", icon="eye", body=body)
                p.text(f"{E.hourglass} *Le fantôme va apparaître… le premier qui frappe **après** son apparition "
                       f"marque. Un faux départ donne le point à l'adversaire !*")
                p.row(button("… pas encore …", "lock", "secondary", self._hit))
            elif self.state == "go":
                p.title(f"Manche {self.round} · FRAPPE !", icon="ghost", body=body)
                p.row(button("FRAPPE !", "ghost", "success", self._hit))
            elif self.state == "pause":
                p.title(f"Manche {self.round} terminée", icon="sparkle", body=body)
            elif self.state == "over":
                p.title(f"{self.winner.display_name} remporte le défi !", icon="crown", body=body)
            elif self.state == "cancel":
                p.title("Défi annulé", icon="cross", body=body)
        p.footer(f"{E.lightning} {a.mention} contre {b.mention} · {MODES[self.mode]}")
        self.add_item(p.container())

    async def update(self, interaction=None):
        self.render()
        try:
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.edit_message(view=self, allowed_mentions=NO_PINGS)
            elif self.message:
                await self.message.edit(view=self, allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            pass

    # ----------------------------------------------------------------- timers
    def later(self, seconds: float, fn):
        """Run ``fn`` after ``seconds`` unless the game moved on in the meantime."""
        self.token += 1
        token = self.token

        async def run():
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.token == token:
                    await fn()
        asyncio.create_task(run())

    # ---------------------------------------------------------------- invite
    async def _accept(self, interaction):
        if interaction.user.id != self.p2.id:
            return await notice(interaction, "Ce défi ne t'est pas destiné.")
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            g = self.guild_id
            if self.stake:
                try:
                    self.store.spend(g, self.p1.id, self.stake, "defi-mise")
                except NotEnough:
                    self.state = "cancel"
                    self.note = f"{self.p1.mention} n'a plus assez de bonbons pour la mise."
                    self.stop()
                    return await self.update(interaction)
                try:
                    self.store.spend(g, self.p2.id, self.stake, "defi-mise")
                except NotEnough:
                    self.store.add_candies(g, self.p1.id, self.stake, "defi-rembourse", boost=False)
                    return await notice(interaction, f"Il te faut **{config.fmt(self.stake)}** bonbons pour accepter.")
                if self.message:
                    self.escrow_key = f"versus:{self.message.id}"
                    self.store.meta_set(self.escrow_key, dict(g=g, players=[self.p1.id, self.p2.id], stake=self.stake))
            await interaction.response.defer()
            await self._next_round()

    async def _decline(self, interaction):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            return await notice(interaction, "Ce défi ne te concerne pas.")
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            self.state = "declined"
            self.token += 1
            self.stop()
            await self.update(interaction)

    async def expire(self):
        if self.state == "invite":
            self.state = "expired"
            self.stop()
            await self.update()

    # ---------------------------------------------------------------- rounds
    async def _next_round(self):
        self.round += 1
        self.locked = set()
        if self.mode == "quiz":
            level = min(5, 1 + self.round // 2)
            self.question, _reset = quiz_bank.pick(level, self.seen)
            self.seen.add(self.question.qid)
            self.choices = [self.question.answer, *self.question.wrong[:3]]
            random.shuffle(self.choices)
            self.state = "question"
            self.deadline = time.time() + QUESTION_TIME
            self.later(QUESTION_TIME, self._quiz_timeout)
        else:
            self.state = "wait"
            self.later(random.uniform(2.0, 6.0), self._go)
        await self.update()

    async def _go(self):
        self.state = "go"
        self.go_at = time.monotonic()
        self.later(10, self._reflex_timeout)
        await self.update()

    async def _quiz_timeout(self):
        if self.state == "question":
            self._point(None, f"{E.hourglass} Temps écoulé ! La réponse était **{self.question.answer}**.")
            await self._after_point()

    async def _reflex_timeout(self):
        if self.state == "go":
            self._point(None, f"{E.hourglass} Personne n'a frappé…")
            await self._after_point()

    def _player(self, interaction):
        uid = interaction.user.id
        return uid if uid in self.score else None

    def _other(self, uid):
        return self.p2 if uid == self.p1.id else self.p1

    def _member(self, uid):
        return self.p1 if uid == self.p1.id else self.p2

    def _answer(self, index: int):
        async def cb(interaction):
            uid = self._player(interaction)
            if uid is None:
                return await notice(interaction, "Tu n'es pas dans ce défi. Lance le tien avec /defi !")
            async with self.lock:
                if self.state != "question":
                    return await interaction.response.defer()
                if uid in self.locked:
                    return await notice(interaction, "Tu t'es déjà trompé sur cette question !", icon="lock")
                if self.choices[index] == self.question.answer:
                    self._point(uid, f"{E.check} **{self._member(uid).display_name}** trouve : **{self.question.answer}**")
                    await interaction.response.defer()
                    return await self._after_point()
                self.locked.add(uid)
                if len(self.locked) == 2:
                    self._point(None, f"{E.cross} Deux erreurs ! La réponse était **{self.question.answer}**.")
                    await interaction.response.defer()
                    return await self._after_point()
                await notice(interaction, f"Raté ! « {self.choices[index]} » n'est pas la bonne réponse.", icon="cross")
                self.note = f"{E.lock} {self._member(uid).display_name} s'est trompé…"
                await self.update()
        return cb

    async def _hit(self, interaction):
        uid = self._player(interaction)
        if uid is None:
            return await notice(interaction, "Tu n'es pas dans ce défi. Lance le tien avec /defi !")
        async with self.lock:
            if self.state == "wait":
                other = self._other(uid)
                self._point(other.id, f"{E.cross} Faux départ de **{self._member(uid).display_name}** : "
                                      f"point pour **{other.display_name}** !")
            elif self.state == "go":
                ms = (time.monotonic() - self.go_at) * 1000
                self._point(uid, f"{E.lightning} **{self._member(uid).display_name}** frappe en **{ms:.0f} ms** !")
            else:
                return await interaction.response.defer()
            await interaction.response.defer()
            await self._after_point()

    def _point(self, uid, line):
        self.token += 1  # cancels the pending timer of this round
        if uid is not None:
            self.score[uid] += 1
        self.history.append(f"`{self.round}` {line}")
        self.note = ""

    async def _after_point(self):
        champion = next((pl for pl in (self.p1, self.p2) if self.score[pl.id] >= WIN_POINTS), None)
        if champion:
            self._finish(champion)
            return await self.update()
        if self.round >= 15:  # endless ties: nobody wins, stakes back
            self._cancel(f"{E.hourglass} Trop de manches nulles : les mises sont rendues.")
            return await self.update()
        self.state = "pause"
        await self.update()
        self.later(2.5, self._next_round)

    def _finish(self, winner):
        g = self.guild_id
        loser = self._other(winner.id)
        self.state = "over"
        self.winner = winner
        if self.stake:
            self.store.add_candies(g, winner.id, self.stake * 2, "defi-gain", boost=False)
        r = grant(self.store, g, winner.id, 0, 25, "duel", stats={"duel_win": 1, "versus_win": 1})
        grant(self.store, g, loser.id, 0, 8, "duel", stats={"duel_loss": 1})
        gain = f"**+{config.fmt(self.stake * 2)}** {E.candy} · " if self.stake else ""
        self.note = f"{E.trophy} {winner.mention} gagne ! {gain}{r.line()}"
        self.stop()

    def _cancel(self, note):
        if self.stake and self.escrow_key:
            for pl in (self.p1, self.p2):
                self.store.add_candies(self.guild_id, pl.id, self.stake, "defi-rembourse", boost=False)
        self.state = "cancel"
        self.note = note
        self.stop()

    def stop(self):
        self.token += 1
        if self.escrow_key:
            self.store.meta_del(self.escrow_key)
            self.escrow_key = None
        super().stop()


class Versus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Refund stakes of challenges interrupted by a restart."""
        for key, info in self.bot.store.meta_prefix("versus:").items():
            for uid in info["players"]:
                self.bot.store.add_candies(info["g"], uid, info["stake"], "defi-rembourse", boost=False)
            self.bot.store.meta_del(key)

    @app_commands.command(name="defi", description="⚡ Défie un membre en direct : quiz éclair ou réflexes")
    @app_commands.describe(adversaire="Qui veux-tu défier ?", mode="Quiz éclair ou duel de réflexes",
                           mise="Bonbons misés par chaque joueur (0 = amical)")
    @app_commands.choices(mode=[app_commands.Choice(name=v, value=k) for k, v in MODES.items()])
    @app_commands.guild_only()
    async def defi(self, interaction: discord.Interaction, adversaire: discord.Member,
                   mode: app_commands.Choice[str], mise: app_commands.Range[int, 0, 100000] = 0):
        if adversaire.bot or adversaire.id == interaction.user.id:
            return await notice(interaction, "Choisis un vrai adversaire (pas toi-même, ni un bot) !")
        if mise and self.bot.store.candies(interaction.guild_id, interaction.user.id) < mise:
            return await notice(interaction, f"Tu n'as pas **{config.fmt(mise)}** bonbons à miser.")
        await interaction.response.defer()
        av1, av2 = await asyncio.gather(avatar_bytes(interaction.user), avatar_bytes(adversaire))
        sub = f"DÉFI {MODES[mode.value].upper()} · PREMIER À {WIN_POINTS}" + (f" · {mise} BONBONS" if mise else "")
        gif = await asyncio.to_thread(versus_gif, interaction.user.display_name, adversaire.display_name, av1, av2, sub,
                                      random.randrange(1000))
        view = VersusView(self.bot, interaction.guild_id, interaction.user, adversaire, mode.value, mise)
        msg = await interaction.followup.send(view=view, files=[image_file(gif, GIF_NAME)], wait=True,
                                              allowed_mentions=discord.AllowedMentions(users=[adversaire]))
        view.message = stable_message(msg) if msg else None
        view.later(61, view.expire)


async def setup(bot):
    await bot.add_cog(Versus(bot))
