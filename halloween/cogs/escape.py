"""/escape — a cooperative escape game: 1 to 4 players, 3 rooms, everyone holds different secret clues."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art.escape import room_png
from ..content import escape as X
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, banner_file, button, image_file, notice, relative, stable_message

MAX_PLAYERS = 4
TIME_LIMIT = 10 * 60
PENALTY = 30
LOBBY_TIME = 120
PNG_NAME = "escape.png"


class CodeModal(discord.ui.Modal, title="Entrer le code"):
    def __init__(self, view: "EscapeView"):
        super().__init__()
        self.view = view
        room = view.room
        self.code = discord.ui.TextInput(label=f"Code ({len(room.code)} caractères)", min_length=1, max_length=12)
        self.add_item(self.code)

    async def on_submit(self, interaction):
        await self.view.try_code(interaction, str(self.code.value))


class EscapeView(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int, host, seed: int | None = None):
        super().__init__(timeout=None)
        self.bot, self.store, self.guild_id = bot, bot.store, guild_id
        self.host = host
        self.players = [host]
        self.rooms = X.make_rooms(seed if seed is not None else random.randrange(10**6))
        self.index = 0
        self.state = "lobby"
        self.deadline = time.time() + LOBBY_TIME
        self.flash = ""
        self.lines: list[str] = []
        self.lock = asyncio.Lock()
        self.message = None
        self.token = 0
        self.render()

    @property
    def room(self) -> X.Room:
        return self.rooms[min(self.index, len(self.rooms) - 1)]

    def seat(self, uid):
        return next((i for i, p in enumerate(self.players) if p.id == uid), None)

    # ----------------------------------------------------------------- render
    def render(self):
        self.clear_items()
        p = Panel("purple")
        names = ", ".join(pl.mention for pl in self.players)
        if self.state == "lobby":
            p.banner("escape")
            p.title("Escape Game : la Crypte", icon="key",
                    body=f"{self.host.mention} ouvre la crypte ! **3 salles**, **10 minutes**, et chaque joueur reçoit "
                         f"des **indices secrets différents** : impossible de s'en sortir sans se parler.\n"
                         f"{E.ghost} Équipe ({len(self.players)}/{MAX_PLAYERS}) : {names}\n"
                         f"{E.hourglass} Départ automatique {relative(self.deadline)}")
            p.row(button("Rejoindre l'équipe", "check", "success", self._join,
                         disabled=len(self.players) >= MAX_PLAYERS),
                  button("Lancer maintenant", "lightning", "primary", self._start))
        elif self.state == "play":
            room = self.room
            p.image(PNG_NAME)
            body = (f"**Salle {self.index + 1}/3** · {room.intro}\n"
                    f"{E.hourglass} Fin du temps {relative(self.deadline)} · une erreur coûte {PENALTY} s\n"
                    f"{E.eye} Chacun clique sur **Mes indices** (visibles par toi seul) et partage-les dans le salon !")
            if self.flash:
                body = self.flash + "\n" + body
            p.title(room.title, icon="lock", body=body)
            p.row(button("Mes indices", "eye", "primary", self._clues),
                  button("Entrer le code", "key", "success", self._ask_code),
                  button("Abandonner", "cross", "danger", self._give_up))
        else:
            won = self.state == "won"
            p.image(PNG_NAME)
            p.title("Évadés de la crypte !" if won else "La crypte vous garde…", icon="sparkle" if won else "skull",
                    body=(self.flash + "\n" if self.flash else "") + "\n".join(self.lines))
        p.footer(f"{E.key} Équipe : {names}")
        self.add_item(p.container())

    async def update(self, interaction=None, attachments=None):
        self.render()
        kwargs = dict(view=self, allowed_mentions=NO_PINGS)
        if attachments is not None:
            kwargs["attachments"] = attachments
        try:
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.edit_message(**kwargs)
            elif interaction is not None:
                await interaction.edit_original_response(**kwargs)
            elif self.message:
                await self.message.edit(**kwargs)
        except discord.HTTPException:
            pass

    def picture(self, opened=False):
        return image_file(room_png(self.index, self.room.title, len(self.room.code), opened, len(self.players)), PNG_NAME)

    # ----------------------------------------------------------------- timers
    def later(self, seconds, fn):
        self.token += 1
        token = self.token

        async def run():
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.token == token:
                    await fn()
        asyncio.create_task(run())

    def arm_lobby(self):
        self.later(LOBBY_TIME, self._begin)

    # ----------------------------------------------------------------- lobby
    async def _join(self, interaction):
        async with self.lock:
            uid = interaction.user.id
            if self.state != "lobby":
                return await interaction.response.defer()
            if self.seat(uid) is not None:
                return await notice(interaction, "Tu fais déjà partie de l'équipe !", icon="check", color="green")
            if len(self.players) >= MAX_PLAYERS:
                return await notice(interaction, "L'équipe est complète.")
            if not self.store.use_play(self.guild_id, uid, "escape"):
                return await notice(interaction, f"Tu as déjà fait tes {config.LIMITS['escape']} escape games aujourd'hui.")
            self.players.append(interaction.user)
            await self.update(interaction)

    async def _start(self, interaction):
        if interaction.user.id != self.host.id:
            return await notice(interaction, "Seul l'organisateur peut lancer la partie.")
        async with self.lock:
            if self.state != "lobby":
                return await interaction.response.defer()
            await interaction.response.defer()
            await self._begin(interaction)

    async def _begin(self, interaction=None):
        self.state = "play"
        self.deadline = time.time() + TIME_LIMIT
        self.later(TIME_LIMIT, self._timeout)
        await self.update(interaction, attachments=[self.picture()])

    # ------------------------------------------------------------------ play
    async def _clues(self, interaction):
        seat = self.seat(interaction.user.id)
        if seat is None:
            return await notice(interaction, "Tu n'es pas enfermé dans cette crypte… lance la tienne avec /escape !")
        if self.state != "play":
            return await interaction.response.defer()
        mine = X.deal(self.room.clues, len(self.players), seat)
        text = "\n".join(f"{E.scroll} {c}" for c in mine)
        await notice(interaction, f"**Tes indices secrets — {self.room.title}**\n{text}\n"
                                  f"-# Les autres joueurs ont d'autres morceaux de l'énigme !", icon="eye", color="purple")

    async def _ask_code(self, interaction):
        if self.seat(interaction.user.id) is None:
            return await notice(interaction, "Tu n'es pas dans cette équipe.")
        if self.state != "play":
            return await interaction.response.defer()
        await interaction.response.send_modal(CodeModal(self))

    async def try_code(self, interaction, text: str):
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            who = interaction.user.display_name
            if X.normalize(text) == X.normalize(self.room.code):
                await interaction.response.defer()
                opened = self.picture(opened=True)
                solved = self.room.title
                self.index += 1
                if self.index >= len(self.rooms):
                    return await self._end(True, interaction, opened)
                self.flash = f"{E.check} **{who}** ouvre « {solved} » ! La salle suivante vous attend…"
                return await self.update(interaction, attachments=[self.picture()])
            self.deadline -= PENALTY
            self.flash = f"{E.cross} **{who}** essaie « {text[:20]} »… raté ! **-{PENALTY} s**"
            if self.deadline <= time.time():
                await interaction.response.defer()
                return await self._end(False, interaction)
            self.later(self.deadline - time.time(), self._timeout)
            await self.update(interaction)

    async def _give_up(self, interaction):
        if interaction.user.id != self.host.id:
            return await notice(interaction, "Seul l'organisateur peut abandonner.")
        async with self.lock:
            if self.state != "play":
                return await interaction.response.defer()
            await interaction.response.defer()
            self.flash = f"{E.cross} L'équipe abandonne."
            await self._end(False, interaction)

    async def _timeout(self):
        if self.state == "play":
            self.flash = f"{E.hourglass} Le temps est écoulé ! Les portes se referment pour toujours…"
            await self._end(False)

    async def _end(self, won: bool, interaction=None, picture=None):
        self.state = "won" if won else "lost"
        self.token += 1
        left = max(0, int(self.deadline - time.time()))
        rooms = self.index
        for pl in self.players:
            if won:
                amount = 200 + 60 * len(self.players) + left // 2
                r = grant(self.store, self.guild_id, pl.id, amount, 40, "escape", stats={"escape_win": 1})
            else:
                r = grant(self.store, self.guild_id, pl.id, 40 * rooms, 8 + 4 * rooms, "escape")
            self.lines.append(f"{pl.mention} {r.line() or '—'}")
        if won:
            mins, secs = divmod(TIME_LIMIT - left, 60)
            self.flash = f"{E.trophy} **Évasion réussie en {mins} min {secs:02d} s !** Toute l'équipe est récompensée."
        else:
            self.flash += f"\n{E.lock} Salles ouvertes : **{rooms}/3**."
        self.stop()
        await self.update(interaction, attachments=[picture or self.picture()])


class Escape(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["escape"] = self.open

    async def open(self, interaction, edit=False):
        if not self.bot.store.use_play(interaction.guild_id, interaction.user.id, "escape"):
            return await notice(interaction, f"Tu as déjà fait tes {config.LIMITS['escape']} escape games aujourd'hui. "
                                             f"Retour {relative(config.next_midnight_ts())}.")
        view = EscapeView(self.bot, interaction.guild_id, interaction.user)
        await interaction.response.send_message(view=view, files=[await banner_file("escape")],
                                                allowed_mentions=NO_PINGS)
        view.message = stable_message(await interaction.original_response())
        view.arm_lobby()

    @app_commands.command(name="escape", description="🗝️ Escape game coopératif : 1 à 4 joueurs, indices secrets, 10 minutes")
    @app_commands.guild_only()
    async def escape(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Escape(bot))
