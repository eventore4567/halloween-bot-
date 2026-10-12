"""/maison — explore a haunted house room by room, find the key, open the crypt."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..content import house as H
from ..emojis import E
from ..rewards import grant
from ..art import scenes
from ..ui import GameView, Panel, button, nav, relative


def clip_sub(kind: str, gained: int, lives: int) -> str:
    """Second line of the action clip: what the outcome changed."""
    if kind in ("treasure", "ghost") and gained > 0:
        return f"+{gained} BONBONS"
    if kind == "trap" and gained < 0:
        return f"{gained} BONBONS"
    if kind == "monster":
        return f"UNE BOUGIE S'ÉTEINT · {lives} RESTANTE{'S' if lives > 1 else ''}"
    if kind == "ghost":
        return "UNE BOUGIE SE RALLUME"
    if kind == "item":
        return "AJOUTÉ À TON SAC"
    return ""


class HouseView(GameView):
    banner_key = "house"
    kicker = "MAISON HANTÉE"
    owner_hint = "Entre dans ta propre maison avec /maison."

    def __init__(self, bot, interaction, allowed: bool):
        super().__init__(bot, interaction, timeout=420)
        self.rooms = random.sample(H.ROOMS, H.DEPTH)
        self.depth = 0
        self.bag = 0
        self.lives = H.LIVES
        self.key = False
        self.event = ""
        self.state = "room" if allowed else "empty"
        self.ending = ""
        self.reward = None

    # ------------------------------------------------------------------ render
    def _status(self):
        candles = E.candle * self.lives + E.bar_m0 * (H.LIVES - self.lives)
        steps = []
        for i in range(H.DEPTH + 1):
            if i < self.depth:
                steps.append(E.check)
            elif i == self.depth and self.state in ("room", "crypt"):
                steps.append(E.house if i < H.DEPTH else E.coffin)
            else:
                steps.append(E.lock if i == H.DEPTH else E.door)
        return (f"{E.candy_bag} Sac : **{config.fmt(self.bag)}** {E.candy} · Bougies {candles}"
                + (f" · {E.key} **clé de la crypte**" if self.key else "") + f"\n{' '.join(steps)}")

    def build(self) -> Panel:
        p = Panel("purple").banner(self.banner_key)
        if self.state == "empty":
            p.title("La maison est fermée pour cette nuit", icon="house",
                    body=f"Tu as déjà fait tes {config.LIMITS['house']} explorations. "
                         f"Les portes se rouvrent {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "end":
            icon = {"crypt": "crown", "escaped": "door", "dead": "skull"}[self.ending]
            title = {"crypt": "Le trésor de la crypte est à toi !", "escaped": "Tu t'échappes de la maison !",
                     "dead": "Ta dernière bougie s'éteint…"}[self.ending]
            p.title(title, icon=icon, body=(self.event + "\n\n" if self.event else "") + self.reward.line())
            p.sep()
            left = self.store.remaining(self.guild_id, self.owner_id, "house")
            p.row(nav("house", self.owner_id, f"Nouvelle exploration ({left})", "house", "success"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        if self.state == "crypt":
            p.title(H.CRYPT["name"], icon=H.CRYPT["emoji"], thumb=E.url(H.CRYPT["emoji"]),
                    body=(self.event + "\n\n" if self.event else "") + H.CRYPT["text"])
            p.text(self._status())
            p.sep()
            p.row(button("Ouvrir la crypte" if self.key else "La grille est verrouillée…", "key", "success",
                         self._crypt, disabled=not self.key),
                  button(f"Sortir avec {config.fmt(self.bag)} bonbons", "door", "secondary", self._leave))
            p.footer(self.footer())
            return p
        room = self.rooms[self.depth]
        p.title(f"Pièce {self.depth + 1}/{H.DEPTH} · {room['name']}", icon=room["emoji"], thumb=E.url(room["emoji"]),
                body=(self.event + "\n\n" if self.event else "") + f"*{room['text']}*")
        p.text(self._status())
        p.sep()
        p.row(*[button(label, emoji, "primary", self._choose(i)) for i, (label, emoji) in enumerate(room["choices"])])
        p.row(button(f"Fuir avec {config.fmt(self.bag)} bonbons", "door", "danger", self._leave))
        p.footer(self.footer("Plus tu avances, plus c'est riche… et dangereux"))
        return p

    # ----------------------------------------------------------------- actions
    def _choose(self, index):
        async def cb(interaction):
            async with self.lock:
                if self.state != "room":
                    return await interaction.response.defer()
                kind = H.outcome(self.depth + 1, self.key)
                room, icon = self.rooms[self.depth]["name"], self.rooms[self.depth]["choices"][index][1]
                gained = self.bag
                self._resolve(kind)
                gained = self.bag - gained
                if self.state == "room":
                    self.depth += 1
                    if self.depth >= H.DEPTH:
                        self.state = "crypt"
                if self.state == "end":
                    return await self.refresh(interaction)  # the end-of-game cutscene takes over
                await interaction.response.defer()
                await self.play_action(interaction, scenes.room_clip, room, icon, kind, None,
                                       clip_sub(kind, gained, self.lives), random.randrange(10**6),
                                       name=self.user.display_name)
        return cb

    def _resolve(self, kind):
        d = self.depth + 1
        g, u = self.guild_id, self.owner_id
        if kind == "treasure":
            amount = H.treasure_amount(d)
            self.bag += amount
            self.event = f"{E.sparkle} {random.choice(H.TREASURES)} **+{amount}** {E.candy}"
        elif kind == "key":
            self.key = True
            self.event = f"{E.key} Tu trouves une **vieille clé rouillée**… Elle ouvre sûrement la crypte !"
        elif kind == "item":
            item = random.choice(["joker", "shield", "ticket"])
            self.store.give_item(g, u, item)
            info = config.SHOP[item]
            self.event = f"{E(info['emoji'])} Tu ramasses un objet : **{info['name']}** (ajouté à ton sac) !"
        elif kind == "trap":
            lost = int(self.bag * 0.35)
            self.bag -= lost
            self.event = f"{E.cross} {random.choice(H.TRAPS)}" + (f" **-{lost}** {E.candy}" if lost else "")
        elif kind == "monster":
            emoji, text = random.choice(H.MONSTERS)
            self.lives -= 1
            self.event = f"{E(emoji)} **{text}** Tu perds une bougie !"
            if self.lives <= 0:
                kept = self.bag // 2
                self.event += f"\nTu t'enfuis dans le noir en lâchant la moitié de ton sac… (**{kept}** {E.candy} sauvés)"
                self.bag = kept
                self._end("dead")
        elif kind == "ghost":
            if self.lives < H.LIVES:
                self.lives += 1
                self.event = f"{E.ghost} Un fantôme bienveillant **rallume une de tes bougies** !"
            else:
                amount = H.treasure_amount(d) // 2
                self.bag += amount
                self.event = f"{E.ghost} Un fantôme bienveillant te souffle une cachette : **+{amount}** {E.candy}"
        else:
            self.event = f"{E.eye} {random.choice(H.EMPTY)}"

    def _end(self, how):
        self.state = "end"
        self.ending = how
        g, u = self.guild_id, self.owner_id
        stats = {"house_escape": 1} if how != "dead" else {"house_dead": 1}
        if how == "crypt":
            stats["crypt"] = 1
        self.reward = grant(self.store, g, u, self.bag, 10 + 6 * self.depth + (25 if how == "crypt" else 0), "maison",
                            stats=stats)
        self.finish()

    async def _crypt(self, interaction):
        async with self.lock:
            if self.state != "crypt" or not self.key:
                return await interaction.response.defer()
            amount = H.crypt_amount(self.bag)
            self.bag += amount
            self.event = (f"{E.coffin} La grille grince… le coffre s'ouvre sur une montagne de bonbons : "
                          f"**+{config.fmt(amount)}** {E.candy} !")
            self._end("crypt")
            await self.refresh(interaction)

    async def _leave(self, interaction):
        async with self.lock:
            if self.state not in ("room", "crypt"):
                return await interaction.response.defer()
            self.event = f"{E.door} Tu claques la porte derrière toi, le cœur battant."
            self._end("escaped")
            await self.refresh(interaction)

    def on_expire(self):
        if self.state in ("room", "crypt"):
            self.event = f"{E.hourglass} Le jour se lève, la maison te recrache dehors."
            self._end("escaped")


class House(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["house"] = self.open

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "house")
        await HouseView(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="maison", description="🏚️ Explore la maison hantée : 4 pièces, une crypte, 3 bougies")
    @app_commands.guild_only()
    async def maison(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(House(bot))
