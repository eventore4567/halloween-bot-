"""/duel — monster rock-paper-scissors between two members, best of 3, with a candy stake."""
from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..art import neon, scroller
from ..ui import ACTION, NO_PINGS, Panel, banner_file, button, image_file, notice, relative, stable_message

MOVES = {
    "vampire": dict(name="Vampire", emoji="vampire", beats="werewolf", verb="mord", color=neon.RED),
    "werewolf": dict(name="Loup-garou", emoji="werewolf", beats="hunter", verb="dévore", color=neon.PINK),
    "hunter": dict(name="Chasseur", emoji="hunter", beats="vampire", verb="plante un pieu dans", color=neon.ORANGE),
}
ROUND_TIME = 45
WINS_NEEDED = 2


def judge(a: str, b: str) -> int:
    """1 if a wins, -1 if b wins, 0 for a draw."""
    if a == b:
        return 0
    return 1 if MOVES[a]["beats"] == b else -1


class DuelView(discord.ui.LayoutView):
    def __init__(self, bot, interaction, opponent: discord.Member, stake: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.store = bot.store
        self.guild_id = interaction.guild_id
        self.p1 = interaction.user
        self.p2 = opponent
        self.stake = stake
        self.state = "invite"
        self.score = {self.p1.id: 0, self.p2.id: 0}
        self.choice: dict[int, str] = {}
        self.history: list[str] = []
        self.round = 1
        self.deadline = time.time() + 60
        self.message = None
        self.lock = asyncio.Lock()
        self.winner = None
        self.note = ""
        self.task: asyncio.Task | None = None
        self.escrow_key = None
        self.clip = None  # (left move, right move, winner side) of the last round, played as a 2D clash
        self.render()

    # ------------------------------------------------------------------ render
    def render(self):
        self.clear_items()
        p = Panel("red")
        if self.clip:
            p.image(ACTION)
        else:
            p.banner("duel")
        a, b = self.p1, self.p2
        stake_txt = f"**{config.fmt(self.stake)}** {E.candy}" if self.stake else "l'honneur"
        rules = (f"{E.hunter} Chasseur bat {E.vampire} Vampire · {E.vampire} Vampire bat {E.werewolf} Loup-garou · "
                 f"{E.werewolf} Loup-garou bat {E.hunter} Chasseur")
        if self.state == "invite":
            p.title("Un duel est lancé !", icon="lightning",
                    body=f"{a.mention} défie {b.mention} pour {stake_txt} !\n"
                         f"Premier à **{WINS_NEEDED} manches**. Le gagnant rafle toute la mise.")
            p.text(f"-# {rules}")
            p.sep()
            p.text(f"{E.hourglass} {b.mention}, accepte {relative(self.deadline)}")
            p.row(button("Accepter le duel", "check", "success", self._accept),
                  button("Refuser", "cross", "danger", self._decline))
        elif self.state in ("play", "over", "cancel"):
            head = {"play": f"Manche {self.round}", "over": "Duel terminé !", "cancel": "Duel annulé"}[self.state]
            p.title(head, icon="lightning",
                    body=f"{a.mention} **{self.score[a.id]}** — **{self.score[b.id]}** {b.mention} · mise : {stake_txt}")
            if self.history:
                p.text("\n".join(self.history[-4:]))
            if self.note:
                p.text(self.note)
            p.sep()
            if self.state == "play":
                status = []
                for pl in (a, b):
                    status.append(f"{E.check if pl.id in self.choice else E.hourglass} {pl.mention} "
                                  + ("a choisi" if pl.id in self.choice else "réfléchit…"))
                p.text(" · ".join(status) + f"\n-# Choisis en secret {relative(self.deadline)} · {rules}")
                p.row(*[button(m["name"], m["emoji"], "secondary", self._play(k)) for k, m in MOVES.items()])
            elif self.state == "over" and self.winner:
                p.text(f"## {E.crown} {self.winner.mention} remporte le duel !")
        else:  # declined / expired
            p.title("Duel refusé" if self.state == "declined" else "Le défi a expiré", icon="cross",
                    body=f"{b.mention} n'a pas relevé le défi de {a.mention}.")
        p.footer(f"{a.mention} contre {b.mention}")
        self.add_item(p.container())

    async def update(self, interaction=None, attachments=None):
        self.render()
        kwargs = dict(view=self, allowed_mentions=NO_PINGS)
        if attachments is not None:
            kwargs["attachments"] = attachments
        try:
            if interaction and not interaction.response.is_done():
                await interaction.response.edit_message(**kwargs)
            elif self.message:
                await self.message.edit(**kwargs)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ timers
    def arm(self, seconds, token):
        if self.task and not self.task.done() and self.task is not asyncio.current_task():
            self.task.cancel()

        async def run():
            await asyncio.sleep(seconds)
            async with self.lock:
                if (self.state, self.round) != token:
                    return
                if self.state == "invite":
                    self.state = "expired"
                    self.stop()
                    await self.update()
                elif self.state == "play":
                    await self._timeout_round()
        self.task = asyncio.create_task(run())

    async def _timeout_round(self):
        missing = [pl for pl in (self.p1, self.p2) if pl.id not in self.choice]
        if len(missing) == 2:
            self._refund()
            self.state = "cancel"
            self.note = f"{E.hourglass} Personne n'a joué… les mises sont rendues."
            self.stop()
        else:
            loser = missing[0]
            winner = self.p1 if loser.id == self.p2.id else self.p2
            self.note = f"{E.hourglass} {loser.mention} n'a pas joué à temps : forfait !"
            self._finish(winner)
        await self.update()

    # ---------------------------------------------------------------- actions
    async def _accept(self, interaction):
        if interaction.user.id != self.p2.id:
            return await notice(interaction, "Ce duel ne t'est pas destiné.")
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            g = self.guild_id
            if self.stake:
                try:
                    self.store.spend(g, self.p1.id, self.stake, "duel")
                except NotEnough:
                    self.state = "cancel"
                    self.note = f"{self.p1.mention} n'a plus assez de bonbons pour la mise."
                    self.stop()
                    return await self.update(interaction)
                try:
                    self.store.spend(g, self.p2.id, self.stake, "duel")
                except NotEnough:
                    self.store.add_candies(g, self.p1.id, self.stake, "duel-rembourse", boost=False)
                    return await notice(interaction, f"Il te faut **{config.fmt(self.stake)}** bonbons pour accepter.")
            if self.stake and self.message:
                self.escrow_key = f"duel:{self.message.id}"
                self.store.meta_set(self.escrow_key, dict(g=g, players=[self.p1.id, self.p2.id], stake=self.stake))
            self.state = "play"
            self.deadline = time.time() + ROUND_TIME
            self.arm(ROUND_TIME + 1, (self.state, self.round))
            await self.update(interaction)

    async def _decline(self, interaction):
        if interaction.user.id not in (self.p2.id, self.p1.id):
            return await notice(interaction, "Ce duel ne te concerne pas.")
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            self.state = "declined"
            self.stop()
            await self.update(interaction)

    def _play(self, move):
        async def cb(interaction: discord.Interaction):
            uid = interaction.user.id
            if uid not in self.score:
                return await notice(interaction, "Tu n'es pas dans ce duel. Lance le tien avec /duel !")
            async with self.lock:
                if self.state != "play":
                    return await interaction.response.defer()
                if uid in self.choice:
                    return await notice(interaction, "Tu as déjà choisi pour cette manche.", icon="hourglass",
                                        color="purple")
                self.choice[uid] = move
                m = MOVES[move]
                await notice(interaction, f"Tu joues **{m['name']}** {E(m['emoji'])} en secret…", icon="check",
                             color="green")
                files = None
                if len(self.choice) == 2:
                    ca, cb_ = self.choice[self.p1.id], self.choice[self.p2.id]
                    self._resolve_round()
                    files = [await self._clash(ca, cb_)]
                await self.update(attachments=files)
        return cb

    async def _clash(self, ca: str, cb_: str):
        """2D clip of the round: both monsters charge, the winner knocks the other away."""
        res = judge(ca, cb_)
        ma, mb = MOVES[ca], MOVES[cb_]
        if res == 0:
            caption, winner = "ÉGALITÉ !", None
        else:
            w, l = (ma, mb) if res > 0 else (mb, ma)
            caption, winner = f"LE {w['name'].upper()} {w['verb'].upper()} LE {l['name'].upper()} !", 0 if res > 0 else 1
        data = await asyncio.to_thread(scroller.clash_gif, ma["emoji"], ma["color"], mb["emoji"], mb["color"],
                                       winner, caption, self.round)
        self.clip = True
        return image_file(data, ACTION)

    def _resolve_round(self):
        a, b = self.p1, self.p2
        ca, cb_ = self.choice[a.id], self.choice[b.id]
        res = judge(ca, cb_)
        ma, mb = MOVES[ca], MOVES[cb_]
        if res == 0:
            line = f"{E(ma['emoji'])} vs {E(mb['emoji'])} — **égalité**, on rejoue !"
        else:
            w, l, mw, ml = (a, b, ma, mb) if res > 0 else (b, a, mb, ma)
            self.score[w.id] += 1
            line = f"{E(ma['emoji'])} vs {E(mb['emoji'])} — le {mw['name']} {mw['verb']} le {ml['name']} : **{w.display_name}** marque !"
        self.history.append(f"`M{self.round}` {line}")
        self.choice = {}
        self.round += 1
        self.note = ""
        champion = next((pl for pl in (a, b) if self.score[pl.id] >= WINS_NEEDED), None)
        if champion:
            self._finish(champion)
        else:
            self.deadline = time.time() + ROUND_TIME
            self.arm(ROUND_TIME + 1, ("play", self.round))

    def _finish(self, winner):
        g = self.guild_id
        loser = self.p1 if winner.id == self.p2.id else self.p2
        self.state = "over"
        self.winner = winner
        if self.stake:
            self.store.add_candies(g, winner.id, self.stake * 2, "duel-gain", boost=False)
        r = grant(self.store, g, winner.id, 0, 20, "duel", stats={"duel_win": 1})
        grant(self.store, g, loser.id, 0, 6, "duel", stats={"duel_loss": 1})
        gain = f"**+{config.fmt(self.stake * 2)}** {E.candy} · " if self.stake else ""
        self.note = (self.note + "\n" if self.note else "") + f"{E.trophy} {gain}{r.line()}"
        if self.task and not self.task.done() and self.task is not asyncio.current_task():
            self.task.cancel()
        self.stop()

    def stop(self):
        if self.escrow_key:
            self.store.meta_del(self.escrow_key)
            self.escrow_key = None
        super().stop()

    def _refund(self):
        if self.stake:
            for pl in (self.p1, self.p2):
                self.store.add_candies(self.guild_id, pl.id, self.stake, "duel-rembourse", boost=False)


class Duel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Refund stakes of duels interrupted by a restart."""
        for key, info in self.bot.store.meta_prefix("duel:").items():
            for uid in info["players"]:
                self.bot.store.add_candies(info["g"], uid, info["stake"], "duel-rembourse", boost=False)
            self.bot.store.meta_del(key)

    @app_commands.command(name="duel", description="⚔️ Défie un membre : Vampire, Loup-garou ou Chasseur ?")
    @app_commands.describe(adversaire="Qui veux-tu défier ?", mise="Bonbons misés par chaque joueur (0 = amical)")
    @app_commands.guild_only()
    async def duel(self, interaction: discord.Interaction, adversaire: discord.Member,
                   mise: app_commands.Range[int, 0, 100000] = 0):
        if adversaire.bot or adversaire.id == interaction.user.id:
            return await notice(interaction, "Choisis un vrai adversaire (pas toi-même, ni un bot) !")
        if mise and self.bot.store.candies(interaction.guild_id, interaction.user.id) < mise:
            return await notice(interaction, f"Tu n'as pas **{config.fmt(mise)}** bonbons à miser.")
        view = DuelView(self.bot, interaction, adversaire, mise)
        await interaction.response.send_message(
            view=view, files=[await banner_file("duel")],
            allowed_mentions=discord.AllowedMentions(users=[adversaire]))
        view.message = stable_message(await interaction.original_response())
        view.arm(61, ("invite", 1))


async def setup(bot):
    await bot.add_cog(Duel(bot))
