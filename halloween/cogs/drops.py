"""Server events: candy drops, flash quizzes and the Pumpkin King raid boss.

They spawn in the channel chosen with /admin salon when the server is
active (every N messages, at most one every few minutes).
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

import discord
from discord.ext import commands

from .. import config
from ..content import quiz_bank
from ..content.games import DROP_SCENES
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, banner_file, button, notice, relative

LOG = logging.getLogger(__name__)
MIN_GAP = 240  # seconds between two automatic events


class EventView(discord.ui.LayoutView):
    """Base for public, first-come events."""

    lifetime = 60

    def __init__(self, cog, guild_id):
        super().__init__(timeout=self.lifetime + 5)
        self.cog = cog
        self.store = cog.bot.store
        self.guild_id = guild_id
        self.message: discord.Message | None = None
        self.lock = asyncio.Lock()
        self.ends = time.time() + self.lifetime
        self.over = False

    def build(self) -> Panel:
        raise NotImplementedError

    def render(self):
        self.clear_items()
        self.add_item(self.build().container())

    async def push(self, interaction=None):
        self.render()
        try:
            if interaction and not interaction.response.is_done():
                await interaction.response.edit_message(view=self, allowed_mentions=NO_PINGS)
            elif self.message:
                await self.message.edit(view=self, allowed_mentions=NO_PINGS)
        except discord.HTTPException as exc:
            LOG.debug("event edit failed: %s", exc)

    async def on_timeout(self):
        if not self.over:
            self.over = True
            await self.expire()
            await self.push()
        self.cog.active.pop(self.guild_id, None)

    async def expire(self):
        pass

    def close(self):
        self.over = True
        self.stop()
        self.cog.active.pop(self.guild_id, None)


class LootView(EventView):
    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        self.scene = random.choice(DROP_SCENES)
        self.amount = random.randint(*self.scene["reward"])
        self.winner = None
        self.reward = None

    def build(self) -> Panel:
        s = self.scene
        p = Panel("orange").banner("drop")
        if self.winner:
            p.title(f"{self.winner.display_name} a été le plus rapide !", icon=s["emoji"], thumb=E.url(s["emoji"]),
                    body=f"{self.winner.mention} rafle le butin : {self.reward.line()}")
        elif self.over:
            p.title("Le butin s'est volatilisé…", icon="ghost",
                    body="Personne n'a été assez rapide. La prochaine fois peut-être !")
        else:
            p.title(s["title"], icon=s["emoji"], thumb=E.url(s["emoji"]),
                    body=f"Le **premier** qui clique gagne **{self.amount}** {E.candy} !\n"
                         f"{E.hourglass} Disparaît {relative(self.ends)}")
            p.row(button(s["button"], s["emoji"], "success", self._grab))
        p.footer("Apparition de la Nuit Hantée · /jeux pour jouer")
        return p

    async def _grab(self, interaction):
        async with self.lock:
            if self.over:
                who = self.winner.mention if self.winner else "personne"
                return await notice(interaction, f"Trop tard ! Le butin est parti avec {who}.", icon="hourglass")
            self.over = True
            self.winner = interaction.user
            self.reward = grant(self.store, self.guild_id, interaction.user.id, self.amount, 10, "apparition",
                                stats={"drops": 1})
            self.close()
            await self.push(interaction)


class FlashQuizView(EventView):
    lifetime = 45

    def __init__(self, cog, guild_id):
        super().__init__(cog, guild_id)
        level = random.choice([2, 2, 3])
        self.q = random.choice(quiz_bank.BY_LEVEL[level])
        self.options, self.correct = self.q.shuffled()
        self.amount = random.randint(120, 260)
        self.out: set[int] = set()
        self.winner = None
        self.reward = None

    def build(self) -> Panel:
        p = Panel("purple").banner("drop")
        if self.winner:
            p.title("Quiz éclair remporté !", icon="crystal",
                    body=f"### {self.q.text}\n{E.check} **{self.options[self.correct]}**\n\n"
                         f"{self.winner.mention} a trouvé en premier : {self.reward.line()}")
        elif self.over:
            p.title("Personne n'a trouvé…", icon="skull",
                    body=f"### {self.q.text}\nLa réponse était **{self.options[self.correct]}**.")
        else:
            p.title("QUIZ ÉCLAIR !", icon="lightning",
                    body=f"Première bonne réponse = **{self.amount}** {E.candy} · une seule tentative par personne !\n"
                         f"### {self.q.text}\n{E.hourglass} Fin {relative(self.ends)}"
                         + (f" · {len(self.out)} éliminé{'s' if len(self.out) > 1 else ''}" if self.out else ""))
            btns = [button(f"{'ABCD'[i]} · {o}"[:80], None, "secondary", self._answer(i))
                    for i, o in enumerate(self.options)]
            p.row(*btns[:2])
            p.row(*btns[2:])
        p.footer("Quiz éclair de la Nuit Hantée · /quiz pour t'entraîner")
        return p

    def _answer(self, i):
        async def cb(interaction):
            uid = interaction.user.id
            async with self.lock:
                if self.over:
                    return await notice(interaction, "Ce quiz éclair est terminé.", icon="hourglass")
                if uid in self.out:
                    return await notice(interaction, "Tu as déjà tenté ta chance sur celui-ci !", icon="lock")
                if i != self.correct:
                    self.out.add(uid)
                    await notice(interaction, "Mauvaise réponse… tu es éliminé de ce quiz éclair !", icon="skull")
                    return await self.push()
                self.winner = interaction.user
                self.reward = grant(self.store, self.guild_id, uid, self.amount, 15, "quiz-eclair",
                                    stats={"quiz_right": 1, "drops": 1})
                self.close()
                await self.push(interaction)
        return cb


class BossView(EventView):
    lifetime = 150
    hit_cooldown = 2.5

    def __init__(self, cog, guild_id, active_players: int):
        super().__init__(cog, guild_id)
        self.hp_max = 600 + 420 * max(1, active_players)
        self.hp = self.hp_max
        self.damage: dict[int, int] = {}
        self.names: dict[int, str] = {}
        self.last_hit: dict[int, float] = {}
        self.feed = ""
        self.dirty = False
        self.last_push = 0.0
        self.flusher: asyncio.Task | None = None
        self.defeated = False
        self.rewards: list[str] = []

    def build(self) -> Panel:
        p = Panel("red").banner("boss")
        hp_line = f"{E.bar(self.hp, self.hp_max, 10)} **{config.fmt(self.hp)}** / {config.fmt(self.hp_max)} PV"
        top = sorted(self.damage.items(), key=lambda kv: -kv[1])[:5]
        medals = [E.medal1, E.medal2, E.medal3, E.skull, E.skull]
        board = "\n".join(f"{medals[i]} <@{uid}> · **{config.fmt(d)}** dégâts" for i, (uid, d) in enumerate(top))
        if self.defeated:
            p.title("LE ROI CITROUILLE EST VAINCU !", icon="crown",
                    body=f"{len(self.damage)} combattants ont sauvé le serveur !\n" + "\n".join(self.rewards[:8]))
        elif self.over:
            p.title("Le Roi Citrouille s'est enfui…", icon="pumpkin_angry",
                    body=f"Il lui restait **{config.fmt(self.hp)}** PV. "
                         f"Chaque combattant reçoit **15** {E.candy} de consolation.")
        else:
            p.title("LE ROI CITROUILLE ATTAQUE !", icon="pumpkin_angry", thumb=E.url("pumpkin_angry"),
                    body=f"Tout le serveur doit frapper ensemble pour le vaincre !\n"
                         f"{E.hourglass} Il s'enfuit {relative(self.ends)}")
        p.text(hp_line + (f"\n{self.feed}" if self.feed and not self.over else ""))
        if board:
            p.sep()
            p.text("### Meilleurs combattants\n" + board)
        if not self.over:
            p.row(button("Frapper !", "lightning", "danger", self._hit),
                  button("Lancer une citrouille", "pumpkin", "primary", self._hit))
        p.footer("Boss de serveur · récompenses selon les dégâts infligés")
        return p

    async def _hit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        now = time.time()
        if self.over:
            return await notice(interaction, "Le combat est terminé.", icon="hourglass")
        if now - self.last_hit.get(uid, 0) < self.hit_cooldown:
            return await interaction.response.defer()
        self.last_hit[uid] = now
        dmg = random.randint(8, 20)
        crit = random.random() < 0.12
        if crit:
            dmg *= 3
        self.hp = max(0, self.hp - dmg)
        self.damage[uid] = self.damage.get(uid, 0) + dmg
        self.feed = (f"{E.fire} **{interaction.user.display_name}** inflige **{dmg}**"
                     + (" — **COUP CRITIQUE !**" if crit else ""))
        await interaction.response.defer()
        if self.hp <= 0 and not self.over:
            await self._victory()
            return
        self._schedule()

    def _schedule(self):
        self.dirty = True
        if self.flusher and not self.flusher.done():
            return

        async def flush():
            wait = max(0.0, 1.6 - (time.time() - self.last_push))
            await asyncio.sleep(wait)
            if self.dirty and not self.over:
                self.dirty = False
                self.last_push = time.time()
                await self.push()
        self.flusher = asyncio.create_task(flush())

    async def _victory(self):
        async with self.lock:
            if self.over:
                return
            self.defeated = True
            ranking = sorted(self.damage.items(), key=lambda kv: -kv[1])
            for i, (uid, d) in enumerate(ranking):
                amount = min(450, 40 + int(d * 0.6)) + (150 if i == 0 else 0)
                r = grant(self.store, self.guild_id, uid, amount, 25, "boss", stats={"boss_win": 1})
                self.rewards.append(f"{E.candy} <@{uid}> · {r.line().splitlines()[0]}"
                                    + (f" {E.crown} *meilleur combattant*" if i == 0 else ""))
            self.close()
            await self.push()

    async def expire(self):
        for uid in self.damage:
            grant(self.store, self.guild_id, uid, 15, 5, "boss")


class Drops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.count: dict[int, int] = {}
        self.goal: dict[int, int] = {}
        self.last: dict[int, float] = {}
        self.active: dict[int, EventView] = {}
        self.authors: dict[int, dict[int, float]] = {}
        self.cfg_cache: dict[int, tuple[float, dict]] = {}

    def cfg(self, guild_id):
        hit = self.cfg_cache.get(guild_id)
        if hit and time.time() - hit[0] < 60:
            return hit[1]
        cfg = self.bot.store.guild(guild_id)
        self.cfg_cache[guild_id] = (time.time(), cfg)
        return cfg

    def active_players(self, guild_id) -> int:
        now = time.time()
        seen = self.authors.get(guild_id, {})
        return sum(1 for ts in seen.values() if now - ts < 600)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        g = message.guild.id
        self.authors.setdefault(g, {})[message.author.id] = time.time()
        cfg = self.cfg(g)
        if not cfg["drop_channel"] or not cfg["drops_on"]:
            return
        self.count[g] = self.count.get(g, 0) + 1
        if g not in self.goal:
            every = cfg["drop_every"]
            self.goal[g] = random.randint(max(5, int(every * 0.6)), int(every * 1.4) + 1)
        if self.count[g] < self.goal[g] or time.time() - self.last.get(g, 0) < MIN_GAP or g in self.active:
            return
        channel = message.guild.get_channel(cfg["drop_channel"])
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        self.count[g] = 0
        self.goal.pop(g, None)
        await self.spawn(channel)

    async def spawn(self, channel, kind: str | None = None):
        g = channel.guild.id
        if kind is None:
            kind = random.choices(["loot", "quiz", "boss"], weights=[50, 35, 15])[0]
        if kind == "boss":
            view = BossView(self, g, self.active_players(g))
            key = "boss"
        elif kind == "quiz":
            view = FlashQuizView(self, g)
            key = "drop"
        else:
            view = LootView(self, g)
            key = "drop"
        view.render()
        try:
            view.message = await channel.send(view=view, files=[await banner_file(key)], allowed_mentions=NO_PINGS)
        except discord.HTTPException as exc:
            LOG.warning("Cannot spawn event in #%s: %s", getattr(channel, "name", "?"), exc)
            return None
        self.active[g] = view
        self.last[g] = time.time()
        return view


async def setup(bot):
    await bot.add_cog(Drops(bot))
