"""/puissance4 — connect four with falling neon discs, against the Witch or a member (with a stake)."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import connect4 as art
from ..content import connect4 as C
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, notice, relative, stable_message

WIN_REWARD, DRAW_REWARD = 180, 60
TURN_TIME = 90
GIF_NAME, PNG_NAME = "puissance4.gif", "puissance4.png"


class Connect4View(GameView):
    banner_key = None
    kicker = "PUISSANCE 4 MAUDIT"
    owner_hint = "Lance ta propre partie avec /puissance4."

    def __init__(self, bot, interaction, allowed: bool = True, opponent=None, stake: int = 0):
        super().__init__(bot, interaction, timeout=900)
        self.p1 = interaction.user
        self.p2 = opponent  # None: the Witch plays
        self.stake = stake if opponent else 0
        self.board = C.new_board()
        self.turn = 1
        self.state = ("invite" if opponent else "play") if allowed else "empty"
        if not allowed:
            self.banner_key = "connect4"
        self.flash = ""
        self.reward = None
        self.winner = 0
        self.animating = False
        self.anim = 0
        self.deadline = time.time() + TURN_TIME
        self.escrow_key = None
        self.escrowed = False
        self.timer = 0

    # ----------------------------------------------------------------- helpers
    def name(self, piece):
        if piece == 1:
            return self.p1.display_name
        return self.p2.display_name if self.p2 else "la Sorcière"

    def mention(self, piece):
        if piece == 1:
            return self.p1.mention
        return self.p2.mention if self.p2 else "**la Sorcière**"

    def player_piece(self, uid):
        if uid == self.p1.id:
            return 1
        if self.p2 and uid == self.p2.id:
            return 2
        return 0

    async def interaction_check(self, interaction):
        if self.player_piece(interaction.user.id):
            return True
        await notice(interaction, "Tu ne joues pas cette partie. Lance la tienne avec /puissance4 !")
        return False

    async def extra_files(self):
        if self.state == "empty":
            return []
        return [image_file(await asyncio.to_thread(art.board_png, self.board), PNG_NAME)]

    # ----------------------------------------------------------------- render
    def build(self) -> Panel:
        p = Panel("orange")
        if self.state == "empty":
            p.banner("connect4")
            p.title("La Sorcière dort", icon="lock",
                    body=f"Plus de parties aujourd'hui. Retour {relative(config.next_midnight_ts())}.")
            p.row(nav("hub", self.owner_id, "Autres jeux", "pumpkin"))
            p.footer(self.footer())
            return p
        p.image(GIF_NAME if self.animating else PNG_NAME)
        vs = f"{E.pumpkin_lit} {self.mention(1)} contre {E.potion_green} {self.mention(2)}"
        stake = f" · mise **{config.fmt(self.stake)}** {E.candy}" if self.stake else ""
        if self.state == "invite":
            p.title("Un Puissance 4 maudit !", icon="lightning",
                    body=f"{vs}{stake}\nAligne **4 pions** en ligne, colonne ou diagonale.\n"
                         f"{E.hourglass} {self.p2.mention}, accepte {relative(self.deadline)}")
            p.row(button("Accepter", "check", "success", self._accept), button("Refuser", "cross", "danger", self._decline))
        elif self.state == "play":
            whose = self.mention(self.turn)
            body = f"{vs}{stake}\nAu tour de {whose} " + (E.pumpkin_lit if self.turn == 1 else E.potion_green)
            if self.p2:
                body += f" · fin du tour {relative(self.deadline)}"
            if self.flash:
                body = self.flash + "\n" + body
            p.title("Puissance 4 maudit", icon="pumpkin_lit", body=body)
            cols = C.valid(self.board)
            p.rows([button(str(c + 1), None, "primary" if self.turn == 1 else "success", self._play(c),
                           disabled=c not in cols or self.animating) for c in range(C.COLS)], per_row=4)
        else:
            if self.state == "cancel":
                title = "Partie annulée"
            elif self.winner:
                title = f"{self.name(self.winner)} gagne !"
            else:
                title = "Match nul !"
            body = (self.flash + "\n" if self.flash else "") + vs + stake
            if self.reward and self.reward.line():
                body += "\n" + self.reward.line()
            p.title(title, icon="crown" if self.winner else "skull", body=body)
            if not self.p2:
                left = self.store.remaining(self.guild_id, self.owner_id, "connect4")
                p.row(nav("connect4", self.owner_id, f"Revanche ({left})", "pumpkin_lit", "success"),
                      nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    # --------------------------------------------------------------- invite
    async def _accept(self, interaction):
        if interaction.user.id != self.p2.id:
            return await notice(interaction, "Cette invitation ne t'est pas destinée.")
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            g = self.guild_id
            if self.stake:
                try:
                    self.store.spend(g, self.p1.id, self.stake, "puissance4-mise")
                except NotEnough:
                    self.state, self.flash = "cancel", f"{self.p1.mention} n'a plus assez de bonbons."
                    self.finish()
                    return await self.refresh(interaction)
                try:
                    self.store.spend(g, self.p2.id, self.stake, "puissance4-mise")
                except NotEnough:
                    self.store.add_candies(g, self.p1.id, self.stake, "puissance4-rembourse", boost=False)
                    return await notice(interaction, f"Il te faut **{config.fmt(self.stake)}** bonbons pour accepter.")
                self.escrowed = True
                if self.message:
                    self.escrow_key = f"c4:{self.message.id}"
                    self.store.meta_set(self.escrow_key, dict(g=g, players=[self.p1.id, self.p2.id], stake=self.stake))
            self.state = "play"
            self.turn = random.choice((1, 2))
            self._arm_turn()
            await self.refresh(interaction)

    async def _decline(self, interaction):
        async with self.lock:
            if self.state != "invite":
                return await interaction.response.defer()
            self.state, self.flash = "cancel", f"{E.cross} Invitation refusée."
            self.finish()
            await self.refresh(interaction)

    def _arm_turn(self):
        """PvP only: a player who does not move in time loses."""
        if not self.p2:
            return
        self.timer += 1
        token, turn = self.timer, self.turn
        self.deadline = time.time() + TURN_TIME

        async def run():
            await asyncio.sleep(TURN_TIME if self.state == "play" else 60)
            async with self.lock:
                if self.timer != token:
                    return
                if self.state == "invite":
                    self.state, self.flash = "cancel", f"{E.hourglass} Le défi a expiré."
                    self.finish()
                elif self.state == "play" and self.turn == turn:
                    self.flash = f"{E.hourglass} {self.name(turn)} n'a pas joué à temps : forfait !"
                    self._end(3 - turn)
                await self.push()
        asyncio.create_task(run())

    def arm_invite(self):
        self.deadline = time.time() + 60
        self._arm_turn()

    # ---------------------------------------------------------------- moves
    def _play(self, col: int):
        async def cb(interaction):
            async with self.lock:
                piece = self.player_piece(interaction.user.id)
                if self.state != "play" or self.animating or col not in C.valid(self.board):
                    return await interaction.response.defer()
                if self.p2 and piece != self.turn:
                    return await notice(interaction, "Ce n'est pas ton tour !", icon="hourglass")
                await interaction.response.defer()
                before = [r[:] for r in self.board]
                moves = [(C.drop(self.board, col, self.turn), col, self.turn)]
                done = self._check(self.turn)
                if not done:
                    self.turn = 3 - self.turn
                    if not self.p2:  # the Witch answers right away
                        wcol = await asyncio.to_thread(C.ai_move, [r[:] for r in self.board], 2)
                        moves.append((C.drop(self.board, wcol, 2), wcol, 2))
                        done = self._check(2)
                        if not done:
                            self.turn = 1
                    else:
                        self._arm_turn()
                win = C.winner_cells(self.board, self.winner) if self.winner else None
                data, seconds = await asyncio.to_thread(art.drop_gif, before, moves, win)
                still = await asyncio.to_thread(art.board_png, self.board, tuple(win or ()))
                self.animating = True
                self.anim += 1
                anim = self.anim
                await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.anim == anim:
                    self.animating = False
                    await self.push(attachments=[image_file(still, PNG_NAME)])
        return cb

    def _check(self, piece) -> bool:
        if C.winner_cells(self.board, piece):
            self._end(piece)
            return True
        if C.full(self.board):
            self._end(0)
            return True
        return False

    def _end(self, winner: int):
        self.state = "over"
        self.winner = winner
        self.timer += 1
        g = self.guild_id
        if self.p2:
            if self.escrowed:
                self.escrowed = False
                if winner:
                    uid = self.p1.id if winner == 1 else self.p2.id
                    self.store.add_candies(g, uid, self.stake * 2, "puissance4-gain", boost=False)
                else:
                    for pl in (self.p1, self.p2):
                        self.store.add_candies(g, pl.id, self.stake, "puissance4-rembourse", boost=False)
            if self.escrow_key:
                self.store.meta_del(self.escrow_key)
                self.escrow_key = None
            if winner:
                w, l = (self.p1, self.p2) if winner == 1 else (self.p2, self.p1)
                self.reward = grant(self.store, g, w.id, 0, 20, "duel", stats={"duel_win": 1, "c4_win": 1})
                grant(self.store, g, l.id, 0, 6, "duel", stats={"duel_loss": 1})
        else:
            amount = WIN_REWARD if winner == 1 else (DRAW_REWARD if winner == 0 else 0)
            self.reward = grant(self.store, g, self.p1.id, amount, 20 if winner == 1 else 6, "puissance4",
                                stats={"c4_win": 1} if winner == 1 else None)
        if winner == 2 and not self.p2:
            self.flash = f"{E.potion_green} La Sorcière ricane : *« Encore un pion pour ma collection ! »*"
        self.finish()

    def on_expire(self):
        if self.state == "play":
            self._end(2 if not self.p2 else 0)


class Connect4(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["connect4"] = self.open

    async def cog_load(self):
        for key, info in self.bot.store.meta_prefix("c4:").items():
            for uid in info["players"]:
                self.bot.store.add_candies(info["g"], uid, info["stake"], "puissance4-rembourse", boost=False)
            self.bot.store.meta_del(key)

    async def open(self, interaction, edit=False):
        allowed = self.bot.store.use_play(interaction.guild_id, interaction.user.id, "connect4")
        await Connect4View(self.bot, interaction, allowed).start(interaction, edit)

    @app_commands.command(name="puissance4", description="🎃 Puissance 4 maudit contre la Sorcière, ou contre un membre")
    @app_commands.describe(adversaire="Défie un membre (laisse vide pour jouer contre la Sorcière)",
                           mise="Bonbons misés par chaque joueur contre un membre")
    @app_commands.guild_only()
    async def puissance4(self, interaction: discord.Interaction, adversaire: discord.Member | None = None,
                         mise: app_commands.Range[int, 0, 100000] = 0):
        if adversaire is None:
            return await self.open(interaction)
        if adversaire.bot or adversaire.id == interaction.user.id:
            return await notice(interaction, "Choisis un vrai adversaire (pas toi-même, ni un bot) !")
        if mise and self.bot.store.candies(interaction.guild_id, interaction.user.id) < mise:
            return await notice(interaction, f"Tu n'as pas **{config.fmt(mise)}** bonbons à miser.")
        view = Connect4View(self.bot, interaction, True, adversaire, mise)
        view.arm_invite()
        view.render()
        files = await view.extra_files()
        await interaction.response.send_message(view=view, files=files,
                                                allowed_mentions=discord.AllowedMentions(users=[adversaire]))
        view.message = stable_message(await interaction.original_response())


async def setup(bot):
    await bot.add_cog(Connect4(bot))
