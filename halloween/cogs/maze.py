"""/labyrinthe — find the key, then the exit, in a foggy maze while a ghost hunts you."""
from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import maze as art
from ..content.maze import DIRS, generate
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

MAX_STEPS = 70
HUNT_RANGE = 6  # the ghost hunts you when it is this close (in steps)
CANDY_VALUE = 15
ESCAPE_REWARD = 150
PNG_NAME = "labyrinthe.png"
ARROWS = [("up", "▲ Haut"), ("left", "◀ Gauche"), ("down", "▼ Bas"), ("right", "Droite ▶")]


def ghost_move(maze, player, turn: int, rnd=random):
    """Hunts when close (2 moves out of 3), wanders otherwise."""
    dist = maze.distances(player).get(maze.ghost, 99)
    if dist <= HUNT_RANGE:
        if turn % 3 == 2:
            return maze.ghost
        return maze.step_towards(maze.ghost, player)
    options = list(maze.neighbours(maze.ghost))
    return rnd.choice(options) if options else maze.ghost


class MazeView(GameView):
    banner_key = None
    kicker = "LABYRINTHE HANTÉ"
    owner_hint = "Entre dans ton propre labyrinthe avec /labyrinthe."

    def __init__(self, bot, interaction, allowed: bool, seed: int | None = None):
        super().__init__(bot, interaction, timeout=600)
        self.state = "play" if allowed else "empty"
        if not allowed:
            self.banner_key = "maze"
        self.maze = generate(seed if seed is not None else random.randrange(10**6))
        self.player = self.maze.start
        self.seen = {self.player}
        self.has_key = False
        self.steps = 0
        self.bag = 0
        self.flash = ""
        self.reward = None

    def picture(self) -> bytes:
        over = self.state in ("caught", "escaped", "lost")
        return art.render(self.maze, self.player, self.seen, self.has_key, self.steps, MAX_STEPS, self.bag,
                          caught=self.state == "caught", escaped=self.state == "escaped", reveal=over)

    async def extra_files(self):
        if self.state == "empty":
            return []
        return [image_file(await asyncio.to_thread(self.picture), PNG_NAME)]

    def _blocked(self, direction) -> bool:
        dx, dy = DIRS[direction]
        nxt = (self.player[0] + dx, self.player[1] + dy)
        return nxt not in set(self.maze.neighbours(self.player))

    def build(self) -> Panel:
        p = Panel("purple")
        if self.state == "empty":
            p.banner("maze")
            p.title("Le labyrinthe est fermé pour la nuit", icon="lock",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        p.image(PNG_NAME)
        if self.state == "play":
            goal = (f"{E.lock} Trouve la **clé** {E.key} cachée dans un coin, puis la **porte** de sortie."
                    if not self.has_key else f"{E.key} Tu as la clé ! File vers la **porte verte** !")
            body = (f"{goal}\n{E.ghost} Un fantôme rôde : s'il te touche, tu perds tout. "
                    f"La {E.candle} bougie le fait fuir.")
            if self.flash:
                body = self.flash + "\n" + body
            p.title("Le Labyrinthe hanté", icon="key", body=body)
            p.row(*[button(label, None, "primary", self._move(d), disabled=self._blocked(d)) for d, label in ARROWS])
            p.row(button("Abandonner", "cross", "danger", self._quit))
        else:
            title = {"escaped": "Évadé !", "caught": "Le fantôme t'a attrapé !", "lost": "Perdu dans le noir…"}[self.state]
            p.title(title, icon="sparkle" if self.state == "escaped" else "skull",
                    body=(self.flash + "\n" if self.flash else "") + self.reward.line())
            left = self.store.remaining(self.guild_id, self.owner_id, "maze")
            p.row(nav("maze", self.owner_id, f"Nouveau labyrinthe ({left})", "key", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    def _move(self, direction):
        async def cb(interaction):
            async with self.lock:
                if self.state != "play" or self._blocked(direction):
                    return await interaction.response.defer()
                dx, dy = DIRS[direction]
                self.player = (self.player[0] + dx, self.player[1] + dy)
                self.steps += 1
                self.seen.add(self.player)
                notes = []
                m = self.maze
                if self.player == m.key and not self.has_key:
                    self.has_key = True
                    notes.append(f"{E.key} **La clé !** La porte de sortie s'illumine.")
                if self.player in m.candies:
                    m.candies.discard(self.player)
                    self.bag += CANDY_VALUE
                    notes.append(f"{E.candy} +{CANDY_VALUE} bonbons ramassés.")
                if self.player == m.candle:
                    m.candle = None
                    far = max(m.distances(self.player).items(), key=lambda kv: kv[1])[0]
                    m.ghost = far
                    notes.append(f"{E.candle} La bougie sacrée chasse le fantôme à l'autre bout du labyrinthe !")
                if self.player == m.exit and self.has_key:
                    self._end("escaped")
                elif self.player == m.ghost:
                    self._end("caught")
                else:
                    m.ghost = ghost_move(m, self.player, self.steps)
                    if m.ghost == self.player:
                        self._end("caught")
                    elif self.steps >= MAX_STEPS:
                        self._end("lost")
                    elif self.player == m.exit:
                        notes.append(f"{E.lock} La porte est verrouillée… il te faut la clé !")
                    elif m.distances(self.player).get(m.ghost, 99) <= 2:
                        notes.append(f"{E.ghost} *Un souffle glacé dans ta nuque… il est tout près !*")
                self.flash = "\n".join(notes)
                await interaction.response.defer()
                data = await asyncio.to_thread(self.picture)
                await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])
        return cb

    async def _quit(self, interaction):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            self._end("lost")
            await interaction.response.defer()
            data = await asyncio.to_thread(self.picture)
            await self.refresh(interaction, attachments=[image_file(data, PNG_NAME)])

    def _end(self, how: str):
        self.state = how
        if how == "escaped":
            bonus = 2 * (MAX_STEPS - self.steps)
            amount = ESCAPE_REWARD + self.bag + bonus
            self.flash = (f"{E.sparkle} Tu t'échappes en **{self.steps} pas** : "
                          f"{ESCAPE_REWARD} + {self.bag} ramassés + {bonus} de bonus de vitesse.")
            self.reward = grant(self.store, self.guild_id, self.owner_id, amount, 25, "labyrinthe",
                                stats={"maze_escape": 1})
        else:
            kept = self.bag // 2 if how == "lost" else 0
            self.flash = (f"{E.ghost} Le fantôme garde tout ton butin." if how == "caught" else
                          f"{E.hourglass} Tu ressors avec la moitié de ton butin.")
            self.reward = grant(self.store, self.guild_id, self.owner_id, kept, 6, "labyrinthe")
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self._end("lost")


class Maze(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["maze"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "maze")
        await MazeView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="labyrinthe", description="🗝️ Le Labyrinthe hanté : trouve la clé et la sortie, fuis le fantôme")
    @app_commands.guild_only()
    async def labyrinthe(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Maze(bot))
