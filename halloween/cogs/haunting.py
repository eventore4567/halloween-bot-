"""La Hantise: the bot turns the server itself into a haunted castle.

``/chateau`` draws the server as a castle: every category is a floor, every
channel a room with its real name, rooms glow with the real activity of the
last 24 hours, and members' avatars stand in the room where they just spoke.

When the server is lively, the Spectre haunts one of its quietest channels.
To chase it, members have to go and talk **in that channel**: a number of
messages from several different people before the time runs out. Exorcised
rooms keep a candle on the castle map, so over October the server lights its
castle back up, and the dead channels come back to life.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..art import castle as art
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, image_file, notice, relative

LOG = logging.getLogger(__name__)

HAUNT_TIME = 30 * 60
NEED_MESSAGES = 12
NEED_PEOPLE = 3
PER_PERSON = 4  # messages of one member that count toward the exorcism
MIN_GAP = 3.0  # seconds between two counted messages of the same member
MIN_ACTIVE = 3
REST = (45 * 60, 120 * 60)  # the Spectre rests this long between two hauntings
SEEN_FOR = 30 * 60  # a member stands in the room where they spoke in the last 30 minutes
DAY = 24 * 3600
MAP, GIF = "chateau.png", "hantise.gif"


def key(g: int) -> str:
    return f"haunt:{g}"


def panel_view(p: Panel) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView(timeout=None)
    v.add_item(p.container())
    return v


def public_rooms(guild, exclude: int | None = None):
    """Channels everybody can read and write in, and where the bot can post pictures."""
    out = []
    me = guild.me
    for ch in getattr(guild, "text_channels", []):
        if ch.id == exclude or getattr(ch, "nsfw", False):
            continue
        everyone = ch.permissions_for(guild.default_role)
        mine = ch.permissions_for(me)
        if everyone.view_channel and everyone.send_messages and mine.send_messages and mine.attach_files:
            out.append(ch)
    return out


class Haunting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.store
        self.lock = asyncio.Lock()
        self.activity: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=400)))
        self.where: dict[int, dict[int, tuple[int, float, object]]] = defaultdict(dict)
        self.last_count: dict[tuple[int, int], float] = {}
        self.avatars: dict[int, tuple[float, bytes | None]] = {}
        self.map_cooldown: dict[int, float] = {}
        self.cache: dict[int, dict | None] = {}  # guild -> state, so ordinary messages never hit the database
        bot.openers["chateau"] = self.open

    # ----------------------------------------------------------------- state
    def state(self, g: int) -> dict:
        if g not in self.cache:
            self.cache[g] = self.store.meta_get(key(g)) or dict(room=None, lit=[], exorcisms=0, next_at=0)
        return self.cache[g]

    def save(self, g: int, st: dict):
        self.cache[g] = st
        self.store.meta_set(key(g), st)

    def events_channel(self, g: int):
        cfg = self.store.guild(g)
        return self.bot.get_channel(cfg["drop_channel"]) if cfg["drop_channel"] else None

    # -------------------------------------------------------------- activity
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        g, now = message.guild.id, time.time()
        cid = message.channel.id
        self.activity[g][cid].append(now)
        where = self.where[g]
        where[message.author.id] = (cid, now, message.author)
        if len(where) > 300:  # forget members who have been silent for a while
            for uid in [u for u, (_, ts, _) in where.items() if now - ts > SEEN_FOR]:
                del where[uid]
        st = self.state(g)
        if st.get("room") != cid:
            return
        u = message.author.id
        if now - self.last_count.get((g, u), 0) < MIN_GAP:
            return
        if now > st.get("deadline", 0):  # too late: the Spectre is leaving, nothing counts any more
            return await self.escape(message.guild)
        async with self.lock:
            st = self.state(g)
            if st.get("room") != cid:
                return
            by = st.setdefault("by", {})
            if by.get(str(u), 0) >= PER_PERSON:
                return
            self.last_count[(g, u)] = now
            by[str(u)] = by.get(str(u), 0) + 1
            done = sum(by.values()) >= NEED_MESSAGES and len(by) >= NEED_PEOPLE
            self.save(g, st)
        if done:
            await self.exorcise(message.guild, message.channel)

    def recent(self, g: int, seconds: float) -> int:
        """How many different members spoke in the last ``seconds``."""
        now = time.time()
        return sum(1 for _, ts, _ in self.where[g].values() if now - ts < seconds)

    def liveliness(self, g: int, cid: int) -> int:
        now = time.time()
        return sum(1 for ts in self.activity[g].get(cid, ()) if now - ts < DAY)

    # -------------------------------------------------------------- the map
    async def avatar(self, member) -> bytes | None:
        now = time.time()
        hit = self.avatars.get(member.id)
        if hit and now - hit[0] < 3600:
            return hit[1]
        if len(self.avatars) > 200:  # forget the avatars fetched more than an hour ago
            for uid in [u for u, (ts, _) in self.avatars.items() if now - ts >= 3600]:
                del self.avatars[uid]
        try:
            data = await member.display_avatar.replace(size=64, static_format="png").read()
        except (discord.HTTPException, ValueError, AttributeError):
            data = None
        self.avatars[member.id] = (time.time(), data)
        return data

    async def floors(self, guild) -> list[art.Floor]:
        g = guild.id
        st = self.state(g)
        rooms = public_rooms(guild)
        counts = {ch.id: self.liveliness(g, ch.id) for ch in rooms}
        top = max(counts.values(), default=0) or 1
        now = time.time()
        people: dict[int, list] = defaultdict(list)
        recent = sorted((v for v in self.where[g].values() if now - v[1] < SEEN_FOR), key=lambda v: -v[1])
        for cid, _, member in recent[:24]:
            people[cid].append((member.id, await self.avatar(member)))
        by_cat: dict[object, list] = defaultdict(list)
        for ch in rooms:
            by_cat[ch.category].append(ch)
        floors = []
        ordered = sorted(by_cat.items(), key=lambda kv: (kv[0] is not None, getattr(kv[0], "position", -1)))
        for cat, chans in ordered:
            chans.sort(key=lambda c: getattr(c, "position", 0))
            # the busiest and the haunted rooms first, when a floor has too many
            keep = sorted(chans, key=lambda c: (c.id != st.get("room"), -counts[c.id]))[:art.MAX_ROOMS]
            keep.sort(key=lambda c: getattr(c, "position", 0))
            floors.append(art.Floor(cat.name if cat else "Hall", [
                art.Room(c.id, c.name, counts[c.id] / top, c.id in st.get("lit", []), people.get(c.id, []))
                for c in keep], more=len(chans) - len(keep)))
        if len(floors) > art.MAX_FLOORS:  # keep the haunted floor, then the liveliest ones, in their order
            haunted = st.get("room")
            ranked = sorted(floors, key=lambda f: (not any(r.cid == haunted for r in f.rooms),
                                                   -sum(r.activity for r in f.rooms)))
            keep = {id(f) for f in ranked[:art.MAX_FLOORS]}
            floors = [f for f in floors if id(f) in keep]
        return floors

    # --------------------------------------------------------------- haunting
    async def haunt(self, guild, channel=None) -> bool:
        """The Spectre settles in ``channel``, or in one of the quietest public channels."""
        g = guild.id
        events = self.events_channel(g)
        async with self.lock:
            st = self.state(g)
            if st.get("room"):
                return False
            options = public_rooms(guild, exclude=getattr(events, "id", None))
            if channel is not None and channel.id not in {c.id for c in options}:
                return False  # private, NSFW, the events channel or no permission: nobody could chase it there
            if channel is None:
                if not options:
                    return False
                options.sort(key=lambda c: self.liveliness(g, c.id))
                calm = self.liveliness(g, options[0].id) * 2 + 2  # only the really quiet ones: wake the dead
                channel = random.choice([c for c in options if self.liveliness(g, c.id) <= calm][:3])
            st.update(room=channel.id, deadline=time.time() + HAUNT_TIME, by={})
            self.save(g, st)
        floors = await self.floors(guild)
        try:
            data = await asyncio.to_thread(art.haunt_gif, guild.name, floors, channel.id,
                                           f"LE SPECTRE HANTE #{art.clean(channel.name).upper()} !")
        except Exception:  # noqa: BLE001 - the haunting goes on without its picture
            LOG.exception("haunt picture failed")
            data = None
        p = Panel("purple")
        if data:
            p.image(GIF)
        p.title("Le Spectre hante ce salon !", icon="ghost",
                body=f"{E.ghost} Il s'est installé ici, dans le silence… Pour le chasser, il faut **{NEED_MESSAGES} "
                     f"messages** de **{NEED_PEOPLE} personnes différentes** dans ce salon avant "
                     f"{relative(st['deadline'])}.\n-# Parlez de tout et de rien : c'est votre voix qui le fait fuir. "
                     f"Chaque exorciste est récompensé.")
        ok = False
        try:
            await channel.send(view=panel_view(p), files=[image_file(data, GIF)] if data else [],
                               allowed_mentions=NO_PINGS)
            ok = True
        except discord.HTTPException as exc:
            LOG.debug("haunt post failed: %s", exc)
        if not ok:  # nobody could see it: the Spectre leaves at once
            async with self.lock:
                st = self.state(g)
                st.update(room=None, by={}, next_at=time.time() + 600)
                self.save(g, st)
            return False
        if events is not None and events.id != channel.id:
            try:
                await events.send(f"{E.ghost} **Le Spectre hante {channel.mention} !** Allez-y à plusieurs pour le "
                                  f"chasser avant {relative(st['deadline'])} (`/chateau` pour voir le château).",
                                  allowed_mentions=NO_PINGS)
            except discord.HTTPException:
                pass
        return True

    async def exorcise(self, guild, channel):
        g = guild.id
        async with self.lock:
            st = self.state(g)
            if st.get("room") != channel.id:
                return
            by = st.get("by", {})
            st["lit"] = sorted(set(st.get("lit", [])) | {channel.id})
            st["exorcisms"] = st.get("exorcisms", 0) + 1
            st.update(room=None, by={}, next_at=time.time() + random.randint(*REST))
            self.save(g, st)
        lines = []
        for uid, n in sorted(by.items(), key=lambda kv: -kv[1]):
            r = grant(self.store, g, int(uid), 30 + 15 * min(n, PER_PERSON), 10, "hantise", stats={"exorcisms": 1})
            lines.append(f"<@{uid}> {r.line()}")
        floors = await self.floors(guild)
        try:
            data = await asyncio.to_thread(art.exorcism_gif, guild.name, floors, channel.id,
                                           f"#{art.clean(channel.name).upper()} EST LIBÉRÉ !")
        except Exception:  # noqa: BLE001
            LOG.exception("exorcism picture failed")
            data = None
        p = Panel("green")
        if data:
            p.image(GIF)
        p.title("Le Spectre est chassé !", icon="sparkle",
                body=f"{E.candle} Une bougie brûle désormais dans {channel.mention} sur la carte du château "
                     f"({st['exorcisms']} salon(s) libéré(s) au total).\n" + "\n".join(lines[:15]))
        try:
            await channel.send(view=panel_view(p), files=[image_file(data, GIF)] if data else [],
                               allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            pass

    async def escape(self, guild):
        """Nobody came: the Spectre slips away (no penalty, the room just stays dark)."""
        g = guild.id
        async with self.lock:
            st = self.state(g)
            room = st.get("room")
            if not room or st.get("deadline", 0) > time.time():
                return False
            st.update(room=None, by={}, next_at=time.time() + random.randint(*REST))
            self.save(g, st)
        channel = self.bot.get_channel(room)
        if channel is not None:
            try:
                await channel.send(f"{E.ghost} *Le Spectre ricane et s'évapore… personne n'est venu le chasser. "
                                   f"Il reviendra.*", allowed_mentions=NO_PINGS)
            except discord.HTTPException:
                pass
        return True

    # ------------------------------------------------------------------ loop
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.tick.is_running():
            self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()

    @tasks.loop(minutes=1)
    async def tick(self):
        for guild in list(self.bot.guilds):
            try:
                await self.step(guild)
            except Exception:  # noqa: BLE001 - one guild must not stop the others
                LOG.exception("haunting tick failed for %s", guild.id)

    async def step(self, guild) -> str:
        g = guild.id
        cfg = self.store.guild(g)
        if not cfg["drop_channel"] or not cfg["drops_on"]:
            return "off"
        st = self.state(g)
        if st.get("room"):
            return "escaped" if await self.escape(guild) else "haunting"
        if time.time() < st.get("next_at", 0) or self.recent(g, 15 * 60) < MIN_ACTIVE:
            return "waiting"
        return "haunted" if await self.haunt(guild) else "no room"

    # -------------------------------------------------------------- commands
    @app_commands.command(name="chateau", description="🏰 Ton serveur en château hanté : qui est où, et où rôde le Spectre")
    @app_commands.guild_only()
    async def chateau(self, interaction: discord.Interaction):
        await self.open(interaction)

    async def open(self, interaction, edit=False):
        g = interaction.guild_id
        if interaction.guild is None:
            return await notice(interaction, "Le château ne se dessine que sur un serveur.")
        if time.time() - self.map_cooldown.get(interaction.user.id, 0) < 30:
            return await notice(interaction, "Le château se redessine… réessaie dans quelques secondes.")
        self.map_cooldown[interaction.user.id] = time.time()
        await interaction.response.defer()
        st = self.state(g)
        floors = await self.floors(interaction.guild)
        data = await asyncio.to_thread(art.map_png, interaction.guild.name, floors, st.get("room"))
        p = Panel("purple")
        p.image(MAP)
        where = (f"{E.ghost} Le Spectre hante <#{st['room']}> : allez-y à plusieurs avant {relative(st['deadline'])} !"
                 if st.get("room") else f"{E.moon} Le Spectre se repose… il reviendra quand le serveur sera animé.")
        p.title(f"Le château de {interaction.guild.name}", icon="house",
                body=f"Chaque étage est une catégorie, chaque pièce un salon. Les pièces brillent avec l'activité des "
                     f"dernières 24 h, et chacun apparaît dans la pièce où il vient de parler.\n{where}\n"
                     f"{E.candle} Salons libérés : **{len(st.get('lit', []))}**")
        await interaction.followup.send(view=panel_view(p), files=[image_file(data, MAP)], allowed_mentions=NO_PINGS)


async def setup(bot):
    await bot.add_cog(Haunting(bot))
