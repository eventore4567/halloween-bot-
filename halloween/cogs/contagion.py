"""La Malédiction contagieuse: a curse that spreads through the server's own chat.

Once a day, when the server is lively, the curse falls on someone who just
spoke. They have 45 minutes to get rid of it by **mentioning another member in
any message**: the curse jumps to that member, and so on. Whoever still holds
it when time runs out loses some candies, and everybody they passed it through
is rewarded. If the chain reaches 12 people, the curse shatters and the whole
chain is rewarded. Every jump is an animated map of the chain, with avatars.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..art import contagion as art
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, fetch_member, image_file, relative

LOG = logging.getLogger(__name__)

HOLD_TIME = 45 * 60
MAX_CHAIN = 12
PENALTY_SHARE = 0.10
PENALTY_MAX = 600
LINK_REWARD = 60  # + LINK_STEP per link in the final chain
LINK_STEP = 15
BREAK_BONUS = 250
MIN_ACTIVE = 3  # members active in the last 10 minutes for the daily curse to strike
GIF_NAME, PNG_NAME = "malediction.gif", "malediction.png"


def key(g: int) -> str:
    return f"contagion:{g}"


def strike_hour(g: int, day: str) -> int:
    """The hour after which today's curse may strike (15 h to 21 h, different each day)."""
    return random.Random(f"contagion:{g}:{day}").randint(15, 21)


def penalty(candies: int) -> int:
    return min(PENALTY_MAX, int(candies * PENALTY_SHARE))


def panel_view(p: Panel) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView(timeout=None)
    v.add_item(p.container())
    return v


class Contagion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.store
        self.locks: dict[int, asyncio.Lock] = {}
        self.holders: dict[int, int | None] = {}  # guild -> holder, so ordinary messages never hit the database

    def holder(self, g: int) -> int | None:
        if g not in self.holders:
            st = self.state(g)
            self.holders[g] = st["holder"] if st else None
        return self.holders[g]

    # ----------------------------------------------------------------- state
    def state(self, g: int) -> dict | None:
        return self.store.meta_get(key(g))

    def lock(self, g: int) -> asyncio.Lock:
        return self.locks.setdefault(g, asyncio.Lock())

    def eligible(self, g: int, member) -> bool:
        """Only members who play (have earned candies) can catch the curse, and never twice in one chain."""
        if member is None or getattr(member, "bot", False):
            return False
        row = self.store.one("SELECT earned FROM players WHERE guild_id=? AND user_id=?", g, member.id)
        if not row or row["earned"] <= 0:
            return False
        st = self.state(g)
        return not st or member.id not in st["chain"]

    def channel(self, g: int):
        cfg = self.store.guild(g)
        return self.bot.get_channel(cfg["drop_channel"]) if cfg["drop_channel"] else None

    async def people(self, guild, chain) -> list[tuple[str, bytes | None]]:
        out = []
        for uid in chain:
            member = await fetch_member(guild, uid)
            name = member.display_name if member else "Fantôme"
            avatar = None
            if member is not None:
                try:
                    avatar = await member.display_avatar.replace(size=128, static_format="png").read()
                except (discord.HTTPException, ValueError, AttributeError):
                    avatar = None
            out.append((name, avatar))
        return out

    async def post(self, channel, p: Panel, data: bytes | None, name: str, ping=None) -> bool:
        if channel is None:
            return False
        files = []
        if data:
            p.children.insert(0, discord.ui.MediaGallery(discord.MediaGalleryItem(media=f"attachment://{name}")))
            files = [image_file(data, name)]
        mentions = discord.AllowedMentions(users=[ping]) if ping is not None else NO_PINGS
        try:
            await channel.send(view=panel_view(p), files=files, allowed_mentions=mentions)
            return True
        except discord.HTTPException as exc:
            LOG.debug("contagion post failed: %s", exc)
            return False

    # ----------------------------------------------------------------- start
    async def start(self, guild, holder, channel=None, day: str | None = None) -> bool:
        g = guild.id
        async with self.lock(g):
            if self.state(g) or not self.eligible(g, holder):
                return False
            st = dict(holder=holder.id, chain=[holder.id], deadline=time.time() + HOLD_TIME,
                      channel=getattr(channel, "id", None))
            self.store.meta_set(key(g), st)
            self.store.meta_set(f"contagion_day:{g}", day or config.today())
            self.holders[g] = holder.id
        p = Panel("purple")
        p.title("La Malédiction contagieuse frappe !", icon="skull_fire",
                body=f"{holder.mention} est **maudit** ! Tu as jusqu'à {relative(st['deadline'])} pour t'en débarrasser : "
                     f"**mentionne un autre joueur** dans n'importe quel message du serveur et la malédiction "
                     f"saute sur lui.\n{E.skull} Celui qui la garde à la fin perd des bonbons, tous ceux qui l'ont "
                     f"refilée sont récompensés. À **{MAX_CHAIN} maillons**, elle se brise : tout le monde gagne !")
        p.footer(f"{E.skull_fire} `/malediction` pour voir la chaîne · seuls les joueurs du bot peuvent l'attraper")
        data = await asyncio.to_thread(art.map_png, await self.people(guild, st["chain"]), HOLD_TIME // 60)
        if not await self.post(channel or self.channel(g), p, data, PNG_NAME, ping=holder):
            # nobody was told: cancel it rather than punish a holder who never knew
            async with self.lock(g):
                self.store.meta_del(key(g))
                self.store.meta_del(f"contagion_day:{g}")
                self.holders[g] = None
            return False
        return True

    # ------------------------------------------------------------------ pass
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.mentions:
            return
        g = message.guild.id
        if self.holder(g) != message.author.id:
            return
        target = next((m for m in message.mentions if m.id != message.author.id and self.eligible(g, m)), None)
        if target is None:
            return
        await self.pass_to(message.guild, target, message)

    async def pass_to(self, guild, target, message=None):
        g = guild.id
        async with self.lock(g):
            st = self.state(g)
            if not st or (message is not None and st["holder"] != message.author.id) or target.id in st["chain"]:
                return
            st["chain"].append(target.id)
            st["holder"] = target.id
            st["deadline"] = time.time() + HOLD_TIME
            broken = len(st["chain"]) >= MAX_CHAIN
            if broken:
                self.store.meta_del(key(g))
            else:
                self.store.meta_set(key(g), st)
            self.holders[g] = None if broken else target.id
        if message is not None:
            try:
                await message.add_reaction("💀")
            except discord.HTTPException:
                pass
        people = await self.people(guild, st["chain"])
        channel = self.bot.get_channel(st["channel"]) if st.get("channel") else self.channel(g)
        if broken:
            return await self.finish(guild, st, broken=True, people=people, channel=channel)
        p = Panel("purple")
        p.title(f"La malédiction passe à {target.display_name} !", icon="skull_fire",
                body=f"{target.mention}, tu es maudit ! Refile-la avant {relative(st['deadline'])} en mentionnant "
                     f"un autre joueur… qui ne l'a pas encore eue.\n{E.scroll} Chaîne : **{len(st['chain'])}/{MAX_CHAIN}** "
                     f"maillons")
        data = await asyncio.to_thread(art.pass_gif, people, random.randrange(10**6))
        await self.post(channel, p, data, GIF_NAME, ping=target)

    # -------------------------------------------------------------------- end
    async def expire(self, guild, now: float | None = None) -> bool:
        g = guild.id
        async with self.lock(g):
            st = self.state(g)
            if not st or st["deadline"] > (now or time.time()):
                return False
            self.store.meta_del(key(g))
            self.holders[g] = None
        channel = self.bot.get_channel(st["channel"]) if st.get("channel") else self.channel(g)
        await self.finish(guild, st, broken=False, people=await self.people(guild, st["chain"]), channel=channel)
        return True

    async def finish(self, guild, st, broken: bool, people, channel):
        g = guild.id
        chain = st["chain"]
        lines = []
        reward = LINK_REWARD + LINK_STEP * len(chain)
        winners = chain if broken else chain[:-1]
        for uid in winners:
            passed = uid != chain[-1]  # the last link of a broken chain is rewarded but passed nothing on
            r = grant(self.store, g, uid, reward + (BREAK_BONUS if broken else 0), 15, "malediction",
                      stats={"curse_passed": 1} if passed else None)
            lines.append(f"<@{uid}> {r.line()}")
        if not broken:
            loser = chain[-1]
            lost = penalty(self.store.candies(g, loser))
            if lost:
                self.store.add_candies(g, loser, -lost, "malediction", boost=False)
            lines.insert(0, f"{E.skull} <@{loser}> garde la malédiction et perd **{config.fmt(lost)}** {E.candy}.")
        p = Panel("green" if broken else "red")
        p.title("Malédiction brisée !" if broken else "La malédiction s'arrête…", icon="sparkle" if broken else "skull",
                body=(f"{E.crown} **{len(chain)} maillons** : la chaîne est complète et la malédiction vole en éclats !"
                      if broken else f"{E.hourglass} Le temps est écoulé. La chaîne compte **{len(chain)}** maillons.")
                     + "\n" + "\n".join(lines))
        p.footer(f"{E.skull_fire} La prochaine malédiction frappera demain, quand le serveur sera actif…")
        data = await asyncio.to_thread(art.final_gif, people, broken, random.randrange(10**6))
        await self.post(channel, p, data, GIF_NAME)

    # ------------------------------------------------------------------- loop
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.tick.is_running():
            self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()

    @tasks.loop(minutes=1)
    async def tick(self):
        now = dt.datetime.now(config.TZ)
        for guild in list(self.bot.guilds):
            try:
                if not await self.expire(guild):
                    await self.maybe_strike(guild, now)
            except Exception:  # noqa: BLE001 - one guild must not stop the others
                LOG.exception("contagion tick failed for %s", guild.id)

    async def maybe_strike(self, guild, now: dt.datetime) -> bool:
        """Today's curse strikes after its hour, on someone who just spoke, if the server is lively."""
        g = guild.id
        cfg = self.store.guild(g)
        if not cfg["drop_channel"] or not cfg["drops_on"] or self.state(g):
            return False
        day = now.strftime("%Y-%m-%d")
        if self.store.meta_get(f"contagion_day:{g}") == day or now.hour < strike_hour(g, day):
            return False
        drops = self.bot.get_cog("Drops")
        seen = drops.authors.get(g, {}) if drops else {}
        recent = [uid for uid, ts in seen.items() if time.time() - ts < 600]
        if len(recent) < MIN_ACTIVE:
            return False
        random.shuffle(recent)
        for uid in recent[:8]:  # a few lookups at most
            member = await fetch_member(guild, uid)
            if self.eligible(g, member):
                return await self.start(guild, member, day=day)
        return False

    # -------------------------------------------------------------- commands
    @app_commands.command(name="malediction", description="💀 La Malédiction contagieuse : qui la porte, et la chaîne")
    @app_commands.guild_only()
    async def malediction(self, interaction: discord.Interaction):
        g = interaction.guild_id
        st = self.state(g)
        p = Panel("purple")
        if not st:
            p.title("Aucune malédiction en cours", icon="skull_fire",
                    body="Une fois par jour, quand le serveur est actif, la **Malédiction contagieuse** tombe sur "
                         "quelqu'un qui vient de parler. Pour s'en débarrasser, il faut **mentionner un autre joueur** "
                         f"dans un message. Celui qui la garde {HOLD_TIME // 60} minutes perd des bonbons ; "
                         f"à {MAX_CHAIN} maillons elle se brise et toute la chaîne gagne.")
            return await interaction.response.send_message(view=panel_view(p), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        people = await self.people(interaction.guild, st["chain"])
        minutes = max(0, int((st["deadline"] - time.time()) // 60))
        data = await asyncio.to_thread(art.map_png, people, minutes)
        p.image(PNG_NAME)
        p.title("La Malédiction contagieuse", icon="skull_fire",
                body=f"{E.skull} Porteur actuel : <@{st['holder']}> (jusqu'à {relative(st['deadline'])})\n"
                     f"{E.scroll} Chaîne : **{len(st['chain'])}/{MAX_CHAIN}** maillons\n"
                     f"-# Pour la refiler : mentionner un joueur qui ne l'a pas encore eue.")
        await interaction.followup.send(view=panel_view(p), files=[image_file(data, PNG_NAME)], ephemeral=True)


async def setup(bot):
    await bot.add_cog(Contagion(bot))
