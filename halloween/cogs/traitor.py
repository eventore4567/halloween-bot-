"""/traitre — Le Traître: a social deduction game for 4 to 12 members of the server.

Vampires hide among the villagers of Brumeval. Roles are handed out secretly
("Mon rôle" answers privately), the night powers are played privately too, and
the whole server debates in the channel before voting to banish a suspect.
Every phase is an animated scene with the players' own avatars.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from ..art import traitor as art
from ..content import traitor as T
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, banner_file, button, image_file, notice, relative, stable_message

LOG = logging.getLogger(__name__)

LOBBY_TIME = 180
NIGHT_TIME = 60
DAY_TIME = 120
VOTE_TIME = 60
VERDICT_TIME = 12
REWARDED_GAMES_PER_DAY = 5
T_NIGHT_PICK = NIGHT_TIME + 10
FILES = {"night": "nuit.gif", "day": "aube.gif", "verdict": "verdict.gif", "over": "fin.gif"}


def win_reward(n_players: int) -> int:
    return 150 + 25 * n_players


class NightPick(discord.ui.LayoutView):
    """The private night action: a select of targets, visible only to the player."""

    def __init__(self, game_view: "TraitorView", uid: int):
        super().__init__(timeout=T_NIGHT_PICK)
        self.gv, self.uid = game_view, uid
        self.night = game_view.game.night
        self.render()

    def render(self, done: str = ""):
        self.clear_items()
        gv, g = self.gv, self.gv.game
        role = T.ROLES[g.role(self.uid)]
        p = Panel(role["color"])
        if done:
            p.title(f"{role['name']} · nuit {self.night}", icon=role["emoji"], body=done)
            self.add_item(p.container())
            return
        intro = {"vampire": "Qui les vampires vont-ils mordre cette nuit ?",
                 "medium": "Sur qui poses-tu ta main de cristal ? Tu verras son vrai rôle.",
                 "guardian": "Qui protèges-tu cette nuit ? (pas la même personne que la nuit dernière)"}[g.role(self.uid)]
        if g.role(self.uid) == "vampire":
            picks = [f"{gv.name(v)} → **{gv.name(t)}**" for v, t in g.bites.items() if v != self.uid]
            if picks:
                intro += "\n-# Les autres vampires visent : " + ", ".join(picks)
        p.title(f"{role['name']} · nuit {self.night}", icon=role["emoji"], body=intro)
        sel = discord.ui.Select(placeholder="Choisis un joueur…", options=[
            discord.SelectOption(label=gv.name(u)[:100], value=str(u)) for u in g.targets(self.uid)][:25])
        sel.callback = self._pick
        p.row(sel)
        self.add_item(p.container())

    async def _pick(self, interaction):
        gv = self.gv
        target = int(interaction.data["values"][0])
        async with gv.lock:
            g = gv.game
            if gv.state != "night" or g.night != self.night:
                self.render(f"{E.hourglass} Trop tard : la nuit est terminée.")
                return await interaction.response.edit_message(view=self)
            try:
                seen = g.act(self.uid, target)
            except ValueError:
                self.render(f"{E.cross} Ce choix n'est plus possible.")
                return await interaction.response.edit_message(view=self)
            role = g.role(self.uid)
            if role == "medium":
                info = T.ROLES[seen]
                text = (f"{E(info['emoji'])} Ta boule de cristal s'illumine : **{gv.name(target)}** est "
                        f"**{info['name']}** !" + ("\n**C'est un vampire !** À toi de convaincre le village… "
                                                  "sans te faire mordre." if seen == "vampire" else ""))
            elif role == "vampire":
                text = f"{E.vampire} Tu as choisi **{gv.name(target)}**. Tu peux encore changer d'avis pendant la nuit."
            else:
                text = f"{E.shield} Tu veilles sur **{gv.name(target)}** cette nuit."
            self.render(text)
            await interaction.response.edit_message(view=self)
            if not g.pending_night():
                await gv.end_night()


class TraitorView(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int, channel_id: int | None, host):
        super().__init__(timeout=None)
        self.bot, self.store, self.guild_id, self.channel_id = bot, bot.store, guild_id, channel_id
        self.host = host
        self.members = {host.id: host}
        self.order = [host.id]
        self.game: T.Game | None = None
        self.state = "lobby"
        self.deadline = time.time() + LOBBY_TIME
        self.flash = ""
        self.lines: list[str] = []
        self.picture: str | None = None
        self.lock = asyncio.Lock()
        self.message = None
        self.token = 0
        self.avatars: dict[int, bytes | None] = {}
        self.render()

    # ---------------------------------------------------------------- helpers
    def name(self, uid: int) -> str:
        m = self.members.get(uid)
        return m.display_name if m else "?"

    def mention(self, uid: int) -> str:
        return f"<@{uid}>"

    async def avatar(self, uid: int) -> bytes | None:
        if uid not in self.avatars:
            try:
                self.avatars[uid] = await self.members[uid].display_avatar.replace(
                    size=128, static_format="png").read()
            except (discord.HTTPException, ValueError, AttributeError):
                self.avatars[uid] = None
        return self.avatars[uid]

    def later(self, seconds, fn):
        self.token += 1
        token = self.token

        async def run():
            await asyncio.sleep(seconds)
            async with self.lock:
                if self.token == token:
                    await fn()
        asyncio.create_task(run())

    async def scene(self, kind: str, make, *args) -> list[discord.File] | None:
        try:
            data = await asyncio.to_thread(make, *args)
        except Exception:  # noqa: BLE001 - a scene must never stop the game
            LOG.exception("traitor scene failed")
            return None
        self.picture = FILES[kind]
        return [image_file(data, FILES[kind])]

    # ----------------------------------------------------------------- render
    def render(self):
        self.clear_items()
        p = Panel("red")
        g = self.game
        if self.state == "lobby":
            p.banner("traitre")
            names = ", ".join(self.mention(u) for u in self.order)
            n = len(self.order)
            p.title("Le Traître : la nuit de Brumeval", icon="vampire",
                    body=f"Des **vampires** se cachent parmi les villageois. La nuit ils mordent, le jour vous débattez "
                         f"et votez pour bannir un suspect. Rôles secrets : **Vampire**, **Médium**, **Gardien**, "
                         f"**Villageois**.\n{E.ghost} Joueurs ({n}/{T.MAX_PLAYERS}) : {names}\n"
                         f"{E.hourglass} Départ {relative(self.deadline)} "
                         f"(il faut au moins **{T.MIN_PLAYERS}** joueurs)")
            p.row(button("Rejoindre", "check", "success", self._join, disabled=n >= T.MAX_PLAYERS),
                  button("Quitter", "door", "secondary", self._leave),
                  button("Lancer la partie", "lightning", "primary", self._start, disabled=n < T.MIN_PLAYERS))
            p.footer(f"{E.vampire} `/traitre` · lancé par {self.host.display_name}")
            self.add_item(p.container())
            return
        if self.picture:
            p.image(self.picture)
        alive = " ".join(f"{E.pumpkin_lit} {self.name(u)}" for u in g.alive)
        dead = " ".join(f"~~{self.name(u)}~~" for u in g.players if u not in g.alive)
        status = f"**En vie ({len(g.alive)})** : {alive}" + (f"\n**Disparus** : {dead}" if dead else "")
        flash = (self.flash + "\n") if self.flash else ""
        if self.state == "night":
            waiting = len(g.pending_night())
            p.title(f"Nuit {g.night} sur Brumeval", icon="moon",
                    body=f"{flash}Tout le monde ferme les yeux… Ceux qui ont un pouvoir cliquent sur **Agir cette nuit**"
                         f" (en secret). Le jour se lève {relative(self.deadline)} "
                         f"ou dès que tous ont agi ({waiting} en attente).")
            p.text(status)
            p.row(button("Mon rôle", "eye", "secondary", self._my_role),
                  button("Agir cette nuit", "moon", "primary", self._act))
        elif self.state == "day":
            ready = len(g.ready)
            p.title(f"Jour {g.night} : le village débat", icon="house",
                    body=f"{flash}{E.scroll} **Discutez dans ce salon** : qui ment ? qui a l'air trop calme ? "
                         f"Le vote commence {relative(self.deadline)}, ou plus tôt si la majorité est prête.")
            p.text(status)
            p.row(button("Mon rôle", "eye", "secondary", self._my_role),
                  button(f"Prêt à voter ({ready}/{len(g.alive)})", "check", "success", self._ready))
        elif self.state == "vote":
            tally = g.tally()
            lines = [f"{self.name(u)} : **{c}** voix" for u, c in tally.most_common()]
            skips = sum(1 for t in g.votes.values() if t == T.SKIP)
            if skips:
                lines.append(f"Personne : **{skips}** voix")
            p.title(f"Jour {g.night} : le vote", icon="skull",
                    body=f"{flash}Qui bannir du village ? Fin du vote {relative(self.deadline)} "
                         f"({len(g.votes)}/{len(g.alive)} ont voté). Égalité = personne n'est banni.\n"
                         + ("\n".join(lines) if lines else "*Aucune voix pour l'instant.*"))
            p.text(status)
            sel = discord.ui.Select(placeholder="Voter contre…", options=[
                discord.SelectOption(label=self.name(u)[:100], value=str(u)) for u in g.alive
            ][:24] + [discord.SelectOption(label="Personne (ne bannir personne)", value=str(T.SKIP))])
            sel.callback = self._vote
            p.row(sel)
            p.row(button("Mon rôle", "eye", "secondary", self._my_role))
        elif self.state == "verdict":
            p.title("Le verdict", icon="fire", body=f"{flash}{E.hourglass} La nuit tombe {relative(self.deadline)}…")
            p.text(status)
            p.row(button("Mon rôle", "eye", "secondary", self._my_role))
        else:  # over
            p.title("Partie terminée", icon="crown", body=flash + "\n".join(self.lines))
        p.footer(f"{E.vampire} Le Traître · {len(g.players)} joueurs · `/traitre` pour rejouer")
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
        except discord.HTTPException as exc:
            LOG.debug("traitor update failed: %s", exc)

    # ------------------------------------------------------------------ lobby
    async def _join(self, interaction):
        async with self.lock:
            uid = interaction.user.id
            if self.state != "lobby":
                return await notice(interaction, "La partie a déjà commencé. Lance la tienne avec `/traitre` !")
            if uid in self.members:
                return await notice(interaction, "Tu es déjà dans la partie !", icon="check", color="green")
            if len(self.order) >= T.MAX_PLAYERS:
                return await notice(interaction, "La partie est complète.")
            self.members[uid] = interaction.user
            self.order.append(uid)
            await self.update(interaction)

    async def _leave(self, interaction):
        async with self.lock:
            uid = interaction.user.id
            if self.state != "lobby" or uid not in self.members:
                return await interaction.response.defer()
            if uid == self.host.id:
                self.state = "over"
                self.token += 1
                self.stop()
                self.game = T.Game.start(self.order)
                self.lines = [f"{E.cross} L'organisateur a annulé la partie."]
                self.picture = None
                return await self.update(interaction)
            self.order.remove(uid)
            del self.members[uid]
            await self.update(interaction)

    async def _start(self, interaction):
        if interaction.user.id != self.host.id:
            return await notice(interaction, "Seul l'organisateur peut lancer la partie.")
        async with self.lock:
            if self.state != "lobby" or len(self.order) < T.MIN_PLAYERS:
                return await interaction.response.defer()
            await interaction.response.defer()
            await self.begin(interaction)

    async def lobby_timeout(self):
        if self.state != "lobby":
            return
        if len(self.order) < T.MIN_PLAYERS:
            self.state = "over"
            self.game = T.Game.start(self.order)
            self.lines = [f"{E.hourglass} Pas assez de joueurs ({len(self.order)}/{T.MIN_PLAYERS}) : "
                          f"la partie est annulée. Relancez avec `/traitre` !"]
            self.stop()
            return await self.update()
        await self.begin()

    async def begin(self, interaction=None):
        self.game = T.Game.start(self.order)
        if self.message is not None and hasattr(self.message, "reply"):
            try:  # one ping so everybody comes back to read their role
                await self.message.reply(
                    f"{E.vampire} La partie commence ! " + " ".join(self.mention(u) for u in self.order)
                    + "\nCliquez sur **Mon rôle** pour découvrir votre rôle secret.",
                    allowed_mentions=discord.AllowedMentions(users=[self.members[u] for u in self.order]))
            except discord.HTTPException:
                pass
        await self.start_night(interaction)

    # ------------------------------------------------------------------ night
    async def start_night(self, interaction=None):
        g = self.game
        g.begin_night()
        self.state = "night"
        self.deadline = time.time() + NIGHT_TIME
        files = await self.scene("night", art.night_gif, g.night, random.randrange(10**6))
        self.later(NIGHT_TIME, self.end_night)
        await self.update(interaction, attachments=files)

    async def end_night(self):
        g = self.game
        if self.state != "night":
            return
        victim, saved = g.resolve_night()
        if victim is None:
            self.flash = f"{E.sparkle} Le soleil se lève… et personne n'a disparu !"
        elif saved:
            self.flash = (f"{E.shield} Les vampires ont attaqué **{self.name(victim)}**… mais le **Gardien** "
                          f"veillait ! Personne n'est mort.")
        else:
            self.flash = (f"{E.skull} **{self.name(victim)}** a été mordu cette nuit. "
                          f"C'était un(e) **{T.ROLES[g.role(victim)]['name']}**.")
        name = self.name(victim) if victim is not None else None
        avatar = await self.avatar(victim) if victim is not None else None
        files = await self.scene("day", art.dawn_gif, name, avatar, saved, g.night, random.randrange(10**6))
        if g.winner():
            return await self.finish(files)
        self.state = "day"
        g.ready.clear()
        self.deadline = time.time() + DAY_TIME
        self.later(DAY_TIME, self.start_vote)
        await self.update(attachments=files)

    async def _act(self, interaction):
        g, uid = self.game, interaction.user.id
        if uid not in self.members:
            return await notice(interaction, "Tu ne joues pas dans cette partie. Lance la tienne avec `/traitre` !")
        if self.state != "night":
            return await notice(interaction, "Ce n'est pas la nuit.")
        if not g.is_alive(uid):
            return await notice(interaction, "Les morts ne peuvent plus agir… mais tu peux observer en silence.",
                                icon="ghost", color="purple")
        role = g.role(uid)
        if role not in T.NIGHT_ROLES:
            return await notice(interaction, f"{E.pumpkin} Tu es **Villageois** : tu dors profondément. "
                                             f"Rendez-vous au lever du jour !", icon="moon", color="purple")
        if role == "medium" and uid in g.looked:
            return await notice(interaction, "Ta boule de cristal s'est éteinte : une seule vision par nuit.",
                                icon="crystal", color="purple")
        await interaction.response.send_message(view=NightPick(self, uid), ephemeral=True)

    # -------------------------------------------------------------------- day
    async def _ready(self, interaction):
        async with self.lock:
            g, uid = self.game, interaction.user.id
            if self.state != "day":
                return await interaction.response.defer()
            if uid not in self.members or not g.is_alive(uid):
                return await notice(interaction, "Seuls les joueurs encore en vie votent.")
            if g.mark_ready(uid):
                await interaction.response.defer()
                return await self.start_vote(interaction)
            await self.update(interaction)

    async def start_vote(self, interaction=None):
        if self.state != "day":
            return
        self.game.begin_vote()
        self.state = "vote"
        self.flash = ""
        self.deadline = time.time() + VOTE_TIME
        self.later(VOTE_TIME, self.end_vote)
        await self.update(interaction)

    async def _vote(self, interaction):
        async with self.lock:
            g, uid = self.game, interaction.user.id
            if self.state != "vote":
                return await interaction.response.defer()
            if uid not in self.members or not g.is_alive(uid):
                return await notice(interaction, "Seuls les joueurs encore en vie votent.")
            target = int(interaction.data["values"][0])
            try:
                g.vote(uid, target)
            except ValueError:
                return await notice(interaction, "Ce joueur n'est plus en vie.")
            if g.all_voted():
                await interaction.response.defer()
                return await self.end_vote(interaction)
            await self.update(interaction)

    async def end_vote(self, interaction=None):
        g = self.game
        if self.state != "vote":
            return
        out = g.resolve_vote()
        if out is None:
            self.flash = f"{E.scroll} Le village n'arrive pas à se décider : personne n'est banni."
            files = None
        else:
            role = T.ROLES[g.role(out)]
            guilty = g.role(out) == "vampire"
            self.flash = (f"{E.fire} Le village bannit **{self.name(out)}**… "
                          + ("C'était un **vampire** !" if guilty else f"C'était un(e) innocent(e) **{role['name']}**…"))
            files = await self.scene("verdict", art.banish_gif, self.name(out), await self.avatar(out), role["name"],
                                     role["emoji"], guilty, random.randrange(10**6))
        if g.winner():
            return await self.finish(None, interaction, prefix=self.flash)
        self.state = "verdict"
        self.deadline = time.time() + VERDICT_TIME
        self.later(VERDICT_TIME, self.start_night)
        await self.update(interaction, attachments=files)

    # ------------------------------------------------------------------ roles
    async def _my_role(self, interaction):
        g, uid = self.game, interaction.user.id
        if g is None or uid not in g.roles:
            return await notice(interaction, "Tu ne joues pas dans cette partie. Lance la tienne avec `/traitre` !")
        info = T.ROLES[g.role(uid)]
        text = f"Tu es **{info['name']}**.\n{info['desc']}"
        if g.role(uid) == "vampire":
            others = [self.name(v) for v in g.vampires(alive_only=False) if v != uid]
            text += ("\n" + E.vampire + " Tes complices : **" + "**, **".join(others) + "**") if others \
                else f"\n{E.vampire} Tu es le seul vampire : à toi de jouer serré."
        if g.role(uid) == "medium" and g.seen.get(uid):
            text += "\n" + E.crystal + " Tes visions : " + ", ".join(
                f"{self.name(t)} = **{T.ROLES[r]['name']}**" for t, r in g.seen[uid].items())
        if not g.is_alive(uid):
            text += f"\n{E.ghost} Tu es mort : ne révèle rien aux vivants !"
        await notice(interaction, text, icon=info["emoji"], color=info["color"])

    # -------------------------------------------------------------------- end
    async def finish(self, files=None, interaction=None, prefix=""):
        g = self.game
        winner = g.winner()
        self.state = "over"
        self.token += 1
        self.stop()
        winners = [u for u in g.players if (g.team(u) == "vampires") == (winner == "vampires")]
        people = [(self.name(u), await self.avatar(u), T.ROLES[g.role(u)]["emoji"]) for u in winners]
        end = await self.scene("over", art.end_gif, winner, people, random.randrange(10**6))
        headline = (f"{E.crown} **Le village a démasqué tous les vampires !**" if winner == "village"
                    else f"{E.vampire} **Les vampires ont pris le contrôle de Brumeval !**")
        self.flash = (prefix + "\n" if prefix else "") + headline
        self.lines = ["**Les rôles :** " + ", ".join(
            f"{self.name(u)} ({T.ROLES[g.role(u)]['name']})" for u in g.players)]
        n = len(g.players)
        for u in g.players:
            won = u in winners
            paid = self.store.bump(self.guild_id, u, "traitor_reward", limit=REWARDED_GAMES_PER_DAY)
            stats = {"traitor_games": 1}
            if won:
                stats["traitor_win"] = 1
                if g.role(u) == "vampire":
                    stats["vampire_win"] = 1
            candies = (win_reward(n) if won else 40) if paid else 0
            r = grant(self.store, self.guild_id, u, candies, (35 if won else 12) if paid else 0, "traitre",
                      stats=stats)
            self.lines.append(f"{self.mention(u)} {r.line() or ('—' if paid else '(récompenses du jour déjà reçues)')}")
        await self.update(interaction, attachments=end or files)


class Traitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active: dict[int, TraitorView] = {}
        bot.openers["traitre"] = self.open

    async def open(self, interaction, edit=False):
        channel_id = interaction.channel_id if hasattr(interaction, "channel_id") else None
        running = self.active.get(channel_id) if channel_id else None
        if running is not None and running.state != "over":
            return await notice(interaction, "Une partie du Traître est déjà en cours dans ce salon !")
        view = TraitorView(self.bot, interaction.guild_id, channel_id, interaction.user)
        if channel_id:
            self.active[channel_id] = view
        await interaction.response.send_message(view=view, files=[await banner_file("traitre")],
                                                allowed_mentions=NO_PINGS)
        view.message = stable_message(await interaction.original_response())
        view.later(LOBBY_TIME, view.lobby_timeout)

    @app_commands.command(name="traitre", description="🧛 Le Traître : des vampires se cachent parmi vous (4 à 12 joueurs)")
    @app_commands.guild_only()
    async def traitre(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Traitor(bot))
