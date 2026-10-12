"""/fuite — La Grande Fuite: a 2D runner where the Reaper chases you through the cemetery.

Each obstacle is a scrolling clip that ends on the next one: jump, slide or strike
before the timer runs out. Every mistake lets the Reaper come closer (3 lives),
the timer gets shorter as you speed up, and from the 8th obstacle the buttons
shuffle. Cash in your bag whenever you like, or reach the chapel for a big bonus.
"""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import runner as art
from ..emojis import E
from ..rewards import grant
from ..ui import ACTION, GameView, Panel, button, image_file, nav, relative

GOAL = 25  # obstacles to the chapel
CHAPEL_BONUS = 400
LIVES = 3
SHUFFLE_FROM = 8  # the buttons shuffle from this obstacle on
CLIP_TIME = 1.7  # seconds the clip plays before the next obstacle shows
UPLOAD_MARGIN = 1.0
ACTIONS = {"jump": "▲ Sauter", "slide": "▼ Glisser", "strike": "✊ Frapper"}
NAMES = {"tomb": "une pierre tombale", "pit": "une fosse", "fireskull": "un crâne en feu",
         "bats": "des chauves-souris", "spider": "une araignée", "coffin": "un cercueil suspendu",
         "zombie": "un zombie", "pumpkin": "une citrouille enragée", "mummy": "une momie"}


def window(passed: int) -> float:
    """Seconds to react once the obstacle is in view: shorter as you speed up."""
    return max(2.5, 6.0 - 0.15 * passed)


def gain(passed: int) -> int:
    """Candies for clearing obstacle number ``passed`` (1-based)."""
    return 8 + 2 * passed


def next_obstacle(previous: str | None, rnd=random) -> str:
    return rnd.choice([k for k in art.OBSTACLES if k != previous])


class RunView(GameView):
    banner_key = "fuite"
    kicker = "LA GRANDE FUITE"
    owner_hint = "Lance ta propre fuite avec /fuite."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=600)
        self.state = "play" if allowed else "empty"
        self.obstacle = next_obstacle(None)
        self.lives = LIVES
        self.passed = 0
        self.bag = 0
        self.flash = ""
        self.reward = None
        self.turn = 0
        self.deadline = 0.0
        self.order = list(ACTIONS)
        self._timer = None
        self._task = None

    # ----------------------------------------------------------------- render
    def build(self) -> Panel:
        p = Panel("red").banner(self.banner_key)
        if self.state == "empty":
            p.title("La Faucheuse se repose", icon="reaper",
                    body=f"Tu as déjà fait tes {config.LIMITS['fuite']} fuites de la nuit. "
                         f"Elle repart en chasse {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "play":
            body = (f"{E.reaper} **La Faucheuse te poursuit !** Obstacle **{self.passed + 1}/{GOAL}** — "
                    f"réagis {relative(self.deadline)} !")
            if self.flash:
                body = self.flash + "\n" + body
            p.title("La Grande Fuite", icon="reaper", body=body)
            hearts = " ".join(str(E.heart) for _ in range(self.lives)) or "—"
            p.text(f"Vies {hearts} · {E.candy_bag} Sac **{config.fmt(self.bag)}** {E.candy} · "
                   f"chapelle à **{GOAL * art.METERS} m**\n"
                   f"-# ▲ Sauter : tombes, fosses, crânes en feu · ▼ Glisser : chauves-souris, araignées, "
                   f"cercueils · ✊ Frapper : zombies, citrouilles, momies"
                   + (" · **les boutons se mélangent !**" if self.passed >= SHUFFLE_FROM else ""))
            p.row(*[button(ACTIONS[a], None, "primary", self._act(a)) for a in self.order])
            p.row(button(f"Encaisser {config.fmt(self.bag)} bonbons", "candy_bag", "success", self._cash,
                         disabled=self.passed == 0))
            p.footer(self.footer("Plus tu cours loin, plus chaque obstacle rapporte"))
            return p
        title = {"escaped": "Tu atteins la chapelle !", "cashed": "Tu te caches avec ton butin",
                 "caught": "La Faucheuse t'a rattrapé…"}[self.state]
        p.title(title, icon="crown" if self.state == "escaped" else "reaper",
                body=(self.flash + "\n" if self.flash else "") + self.reward.line())
        left = self.store.remaining(self.guild_id, self.owner_id, "fuite")
        p.row(nav("fuite", self.owner_id, f"Nouvelle fuite ({left})", "reaper", "success"),
              nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def extra_files(self):
        if self.state != "play":
            return []
        data = await asyncio.to_thread(art.start_clip, self.obstacle, self.user.display_name, random.randrange(10**6))
        self._action = ACTION
        self._set_deadline()
        return [image_file(data, ACTION)]

    async def start(self, interaction, edit=False):
        await super().start(interaction, edit)
        if self.state == "play":
            self._arm()

    # ------------------------------------------------------------------ timer
    def _set_deadline(self):
        self.deadline = time.time() + CLIP_TIME + UPLOAD_MARGIN + window(self.passed)

    def _arm(self):
        """Too slow = a miss: the Reaper comes closer even if the player does nothing."""
        self.turn += 1
        token = self.turn
        if self._timer:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(max(0.5, self.deadline - time.time() + 0.5), self._spawn, token)

    def _spawn(self, token):
        self._task = asyncio.ensure_future(self._expire(token))  # keep a reference until it runs

    async def _expire(self, token):
        async with self.lock:
            if token != self.turn or self.state != "play":
                return
            await self._step(None, None)

    # ---------------------------------------------------------------- actions
    def _act(self, action):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play":
                    return await interaction.response.defer()
                late = time.time() > self.deadline
                await interaction.response.defer()
                await self._step(None if late else action, interaction)
        return cb

    async def _step(self, action, interaction):
        kind = self.obstacle
        ok = action == art.OBSTACLES[kind]
        lives_before = self.lives
        if ok:
            self.passed += 1
            got = gain(self.passed)
            self.bag += got
            self.flash = f"{E.check} Tu passes {NAMES[kind]} ! **+{got}** {E.candy}"
        else:
            self.lives -= 1
            self.flash = (f"{E.cross} " + ("Trop lent !" if action is None else "Mauvais geste !")
                          + f" {NAMES[kind].capitalize()} te fait trébucher… la Faucheuse se rapproche.")
        if self.lives <= 0:
            return await self._end("caught", interaction)
        if self.passed >= GOAL:
            return await self._end("escaped", interaction)
        self.obstacle = next_obstacle(kind)
        if self.passed >= SHUFFLE_FROM:
            random.shuffle(self.order)
        try:
            data = await asyncio.to_thread(art.step_clip, kind, action, ok, self.obstacle, lives_before, self.lives,
                                           self.passed, self.bag, self.user.display_name, random.randrange(10**6))
        except Exception:  # noqa: BLE001 - a clip must never break the game
            data = None
        self._set_deadline()
        files = [image_file(data, ACTION)] if data else None
        self._action = ACTION if data else getattr(self, "_action", None)
        if interaction is not None:
            await self.refresh(interaction, attachments=files)
        else:
            await self.push(attachments=files)
        self._arm()

    async def _cash(self, interaction):
        async with self.lock:
            if self.state != "play" or self.passed == 0:
                return await interaction.response.defer()
            await interaction.response.defer()
            await self._end("cashed", interaction)

    def _pay(self, how: str):
        self.state = how
        if self._timer:
            self._timer.cancel()
        self.turn += 1
        meters = self.passed * art.METERS
        if how == "escaped":
            amount, xp = self.bag + CHAPEL_BONUS, 40
            self.flash = (f"{E.sparkle} **{GOAL} obstacles** franchis : la Faucheuse ne peut pas entrer dans la "
                          f"chapelle ! Bonus de **{CHAPEL_BONUS}** {E.candy}.")
        elif how == "cashed":
            amount, xp = self.bag, 5 + self.passed
            self.flash = f"{E.candy_bag} Tu t'arrêtes après **{meters} m** et gardes tout ton sac."
        else:
            amount, xp = self.bag // 4, 5 + self.passed
            self.flash = (f"{E.reaper} Rattrapé après **{meters} m** : elle te laisse un quart du sac."
                          if self.bag else f"{E.reaper} Rattrapé après **{meters} m**.")
        self.reward = grant(self.store, self.guild_id, self.owner_id, amount, xp, "fuite",
                            stats={"run_obstacles": self.passed}, best={"run_best": self.passed})
        self.finish()

    async def _end(self, how, interaction):
        self._pay(how)
        if interaction is not None:
            await self.refresh(interaction)  # the end-of-game cutscene takes over
        else:
            await self.push()

    def on_expire(self):
        if self.state == "play":
            self._pay("cashed" if self.passed else "caught")


class Runner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["fuite"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "fuite")
        if not interaction.response.is_done():
            await interaction.response.defer()  # the opening clip takes a moment to draw
        await RunView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="fuite", description="💀 La Grande Fuite : saute, glisse, frappe… la Faucheuse te poursuit !")
    @app_commands.guild_only()
    async def fuite(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Runner(bot))
