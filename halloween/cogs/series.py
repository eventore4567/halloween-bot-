"""La Série hantée: an interactive horror series, one episode every evening in the events channel.

Members of the server play the three main parts (picked among the most active
players at the start of each season). Each episode ends on a choice: the whole
server votes with buttons until the next episode, the winning choice is told at
the start of the next one and steers the finale (four endings). A new season
starts with a new cast after the finale.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import re
from collections import Counter

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..art import series as art
from ..content import series as S
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, STYLE, Panel, image_file, notice, register_dynamic

LOG = logging.getLogger(__name__)

RELEASE_HOUR = 21
VOTE_REWARD = 20
ROLES = [("hero", "LE HÉROS"), ("suspect", "LE SUSPECT"), ("victim", "LA PROIE")]
EXTRAS = ["Ambroise le fossoyeur", "la petite Lison", "le maire Bertrand"]
GIF_NAME = "episode.gif"


def key(g: int) -> str:
    return f"series:{g}"


class SeriesVote(discord.ui.DynamicItem[discord.ui.Button], template=r"nh:sv:(?P<season>\d+):(?P<ep>\d+):(?P<k>\d)"):
    """A vote button that keeps working after the bot restarts."""

    def __init__(self, season: int, ep: int, k: int, label: str, emoji: str):
        super().__init__(discord.ui.Button(label=label[:80], emoji=E.partial(emoji), style=STYLE["primary"],
                                           custom_id=f"nh:sv:{season}:{ep}:{k}"))
        self.season, self.ep, self.k = season, ep, k

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        inst = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(inst, item)
        inst.season, inst.ep, inst.k = int(match["season"]), int(match["ep"]), int(match["k"])
        return inst

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Series")
        await cog.vote(interaction, self.season, self.ep, self.k)


class Series(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.store
        self.lock = asyncio.Lock()
        register_dynamic(bot, SeriesVote)

    def state(self, g: int) -> dict | None:
        return self.store.meta_get(key(g))

    # ------------------------------------------------------------------ cast
    def pick_cast(self, guild) -> list[list]:
        """[uid or None, name] for the hero, the suspect and the victim."""
        rows = self.store.board(guild.id, "earned", 25)
        members = [m for m in (guild.get_member(uid) for uid, _ in rows) if m is not None and not m.bot]
        chosen = random.sample(members, min(3, len(members)))
        cast = [[m.id, m.display_name] for m in chosen]
        extras = [x for x in EXTRAS]
        while len(cast) < 3:
            cast.append([None, extras.pop(0)])
        return cast

    def names(self, guild, st) -> dict[str, str]:
        out = {}
        for (role, _), (uid, name) in zip(ROLES, st["cast"]):
            member = guild.get_member(uid) if uid and guild else None
            out[role] = member.display_name if member else name
        return out

    async def avatars(self, guild, st) -> list[bytes | None]:
        out = []
        for uid, _ in st["cast"]:
            member = guild.get_member(uid) if uid and guild else None
            data = None
            if member is not None:
                try:
                    data = await member.display_avatar.replace(size=128, static_format="png").read()
                except (discord.HTTPException, ValueError, AttributeError):
                    data = None
            out.append(data)
        return out

    # --------------------------------------------------------------- release
    def resolve(self, st) -> str:
        """Count the votes of the episode on air; returns the outcome told in the next episode."""
        ep = S.EPISODES[st["ep"]]
        if not ep.choices:
            return ""
        counts = Counter(st["votes"].values())
        if counts:
            top = max(counts.values())
            k = random.choice(sorted(int(c) for c, n in counts.items() if n == top))
            how = f"Le serveur a choisi : **{ep.choices[k].label}** ({top} voix)."
        else:
            k = random.randrange(len(ep.choices))
            how = f"Personne n'a voté… le destin a choisi : **{ep.choices[k].label}**."
        choice = ep.choices[k]
        st["totals"][choice.leaning] = st["totals"].get(choice.leaning, 0) + 1
        return how + "\n" + choice.outcome

    async def release(self, guild, channel=None, day: str | None = None) -> bool:
        g = guild.id
        cfg = self.store.guild(g)
        channel = channel or (self.bot.get_channel(cfg["drop_channel"]) if cfg["drop_channel"] else None)
        if channel is None:
            return False
        async with self.lock:
            st = self.state(g)
            outcome = ""
            if st and st["ep"] < len(S.EPISODES) - 1:
                outcome = self.resolve(st)
                st["ep"] += 1
            else:  # a new season (or the very first one)
                st = dict(season=(st["season"] + 1) if st else 1, ep=0, cast=self.pick_cast(guild), totals={})
            st["prev"] = outcome
            st["votes"] = {}
            st["day"] = day or config.today()
            st["channel"] = channel.id
            self.store.meta_set(key(g), st)
        await self.post(guild, channel, st)
        return True

    def episode_panel(self, guild, st) -> tuple[Panel, dict]:
        ep = S.EPISODES[st["ep"]]
        cast = self.names(guild, st)
        p = Panel("purple")
        p.image(GIF_NAME)
        finale = not ep.choices
        prev = ""
        if st.get("prev"):
            prev = f"{E.scroll} **Précédemment…** {S.fill(st['prev'], cast)}\n\n"
        if finale:
            end_key = S.ending(st["totals"])
            title, text = S.ENDINGS[end_key]
            p.title(f"{S.SEASON_TITLE} · {ep.title}", icon="crown",
                    body=f"{prev}### {title}\n{S.fill(text, cast)}")
            p.text(f"-# Fin de la saison {st['season']} ! Une nouvelle saison, avec un nouveau casting, "
                   f"commence demain à {RELEASE_HOUR} h.")
        else:
            p.title(f"{S.SEASON_TITLE} · Épisode {st['ep'] + 1}/{len(S.EPISODES)} : {ep.title}", icon="book",
                    body=f"{prev}{S.fill(ep.text, cast)}\n\n**Que doit faire le village ?** Votez avant demain "
                         f"{RELEASE_HOUR} h ({VOTE_REWARD} {E.candy} pour chaque votant).")
            p.row(*[SeriesVote(st["season"], st["ep"], k, S.fill(c.label, cast), c.emoji)
                    for k, c in enumerate(ep.choices)])
        p.footer(f"{E.book} La Série hantée · saison {st['season']} · avec "
                 f"{cast['hero']}, {cast['suspect']} et {cast['victim']} · `/serie` pour le résumé")
        return p, cast

    async def post(self, guild, channel, st):
        ep = S.EPISODES[st["ep"]]
        p, cast = self.episode_panel(guild, st)
        roles = [(label, cast[role]) for role, label in ROLES]
        avatars = await self.avatars(guild, st)
        finale = not ep.choices
        end_key = S.ending(st["totals"]) if finale else None
        try:
            data = await asyncio.to_thread(
                art.episode_gif, st["ep"] + 1, ep.title, ep.place,
                [(label, name, av) for (label, name), av in zip(roles, avatars)],
                S.ENDINGS[end_key][0] if finale else None, end_key != "soupcon", random.randrange(10**6))
            files = [image_file(data, GIF_NAME)]
        except Exception:  # noqa: BLE001 - the episode must air even without its picture
            LOG.exception("episode picture failed")
            p.children = [c for c in p.children if not isinstance(c, discord.ui.MediaGallery)]
            files = []
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(p.container())
        ping = [guild.get_member(uid) for uid, _ in st["cast"] if uid] if st["ep"] in (0, len(S.EPISODES) - 1) else []
        mentions = discord.AllowedMentions(users=[m for m in ping if m]) if ping else NO_PINGS
        content_ping = " ".join(m.mention for m in ping if m)
        try:
            if content_ping:  # the cast is told they are in the story (episode 1 and finale only)
                await channel.send(f"{E.book} {content_ping} : vous êtes dans la série !", allowed_mentions=mentions)
            await channel.send(view=view, files=files, allowed_mentions=NO_PINGS)
        except discord.HTTPException as exc:
            LOG.debug("episode post failed: %s", exc)

    # ------------------------------------------------------------------ vote
    async def vote(self, interaction, season: int, ep: int, k: int):
        g, u = interaction.guild_id, interaction.user.id
        async with self.lock:
            st = self.state(g)
            if not st or st["season"] != season or st["ep"] != ep:
                return await notice(interaction, "Cet épisode est terminé : regarde le dernier épisode !")
            first = str(u) not in st["votes"]
            st["votes"][str(u)] = k
            self.store.meta_set(key(g), st)
        choices = S.EPISODES[ep].choices
        cast = self.names(interaction.guild, st)
        counts = Counter(st["votes"].values())
        tally = " · ".join(f"{S.fill(c.label, cast)} : **{counts.get(i, 0)}**" for i, c in enumerate(choices))
        line = ""
        if first:
            r = grant(self.store, g, u, VOTE_REWARD, 5, "serie", stats={"series_votes": 1})
            line = "\n" + r.line()
        await notice(interaction, f"Ton vote : **{S.fill(choices[k].label, cast)}**{line}\n-# {tally}",
                     icon="check", color="purple")

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
                await self.maybe_release(guild, now)
            except Exception:  # noqa: BLE001 - one guild must not stop the others
                LOG.exception("series tick failed for %s", guild.id)

    async def maybe_release(self, guild, now: dt.datetime) -> bool:
        cfg = self.store.guild(guild.id)
        if not cfg["drop_channel"] or now.hour < RELEASE_HOUR:
            return False
        day = now.strftime("%Y-%m-%d")
        st = self.state(guild.id)
        if st and st.get("day") == day:
            return False
        return await self.release(guild, day=day)

    # -------------------------------------------------------------- commands
    @app_commands.command(name="serie", description="📖 La Série hantée : le résumé et l'épisode en cours")
    @app_commands.guild_only()
    async def serie(self, interaction: discord.Interaction):
        st = self.state(interaction.guild_id)
        p = Panel("purple")
        if not st:
            p.title("La Série hantée", icon="book",
                    body=f"Chaque soir à **{RELEASE_HOUR} h**, un nouvel épisode d'une histoire d'horreur sort dans le "
                         f"salon des événements. Les **membres du serveur** en sont les personnages, et c'est le "
                         f"serveur qui **vote** pour la suite !\n-# Le premier épisode sortira ce soir (si le salon des "
                         f"événements est réglé).")
        else:
            cast = self.names(interaction.guild, st)
            ep = S.EPISODES[st["ep"]]
            counts = Counter(st["votes"].values())
            lines = "\n".join(f"{E(c.emoji)} {S.fill(c.label, cast)} : **{counts.get(i, 0)}** voix"
                              for i, c in enumerate(ep.choices))
            p.title(f"{S.SEASON_TITLE} · saison {st['season']}", icon="book",
                    body=f"**Épisode {st['ep'] + 1}/{len(S.EPISODES)} : {ep.title}**\n"
                         f"{E.ghost} Avec **{cast['hero']}** (le héros), **{cast['suspect']}** (le suspect) et "
                         f"**{cast['victim']}** (la proie)\n" + (lines or "Saison terminée !")
                         + f"\n-# Prochain épisode ce soir à {RELEASE_HOUR} h dans <#{st['channel']}>.")
        view = discord.ui.LayoutView()
        view.add_item(p.container())
        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Series(bot))
