"""/tresor — La Chasse au trésor du serveur: four enigmas hidden all over the server.

1. a coded message on a cipher wheel (in /tresor),
2. a parchment hidden in **another channel** of the server (only a hint says which one),
3. a word written backwards in the **bot's nickname** on the server,
4. a word-search grid.
Everybody hunts at once, each at their own pace; the first to solve all four wins
the big prize, the next ones smaller prizes. Organisers start it with
``/reglages lancer-chasse-tresor``; it lasts 24 hours.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config
from ..art import neon, scenes
from ..art import treasure as art
from ..content import treasure as T
from ..emojis import E
from ..rewards import grant
from ..ui import NO_PINGS, Panel, image_file, notice, relative
from .profile import avatar_bytes

LOG = logging.getLogger(__name__)

DURATION = 24 * 3600
PRIZES = [1500, 800, 500]
FINISH_PRIZE = 200
STEP_PRIZE = 40
WRONG_COOLDOWN = 8
PODIUM_SHOWN = 15  # the final message stays far below Discord's 4 000 characters
PNG = ["enigme1.png", "parchemin.png", None, "grille.png"]


def key(g: int) -> str:
    return f"treasure:{g}"


def panel_view(p: Panel) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView(timeout=None)
    v.add_item(p.container())
    return v


def hidden_spot(guild, exclude_id) -> discord.TextChannel | None:
    """A channel everybody can read and the bot can write in, other than the events channel."""
    me = guild.me
    options = []
    for ch in getattr(guild, "text_channels", []):
        if ch.id == exclude_id:
            continue
        everyone = ch.permissions_for(guild.default_role)
        mine = ch.permissions_for(me)
        if everyone.view_channel and everyone.read_message_history and mine.send_messages and mine.attach_files:
            options.append(ch)
    return random.choice(options) if options else None


class Treasure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = bot.store
        self.wrong: dict[tuple[int, int], float] = {}
        self.lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()  # two organisers launching at once must not create two hunts

    def state(self, g: int) -> dict | None:
        return self.store.meta_get(key(g))

    # ----------------------------------------------------------------- start
    async def start(self, guild, event_channel) -> str | None:
        """Start a hunt; returns an error message, or None when it started."""
        async with self.start_lock:
            return await self._start(guild, event_channel)

    async def _start(self, guild, event_channel) -> str | None:
        g = guild.id
        if self.state(g):
            return "Une chasse au trésor est déjà en cours."
        seed = random.randrange(10**9)
        hunt = T.make_hunt(seed)
        spot = hidden_spot(guild, getattr(event_channel, "id", None)) or event_channel
        if spot is None:
            return "Je ne trouve aucun salon où cacher le parchemin."
        p = Panel("orange")
        p.image(PNG[1])
        p.title("Un parchemin mystérieux…", icon="scroll",
                body=f"{E.key} Une pièce de la **Chasse au trésor** est cachée ici. Si tu cherches l'énigme 2, "
                     f"tu l'as trouvée ! (`/tresor` pour jouer)")
        try:
            await spot.send(view=panel_view(p), files=[image_file(art.scroll_png(hunt.anagram), PNG[1])],
                            allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            return "Impossible de cacher le parchemin (permissions)."
        name = spot.name
        clue_in_nick = await self.set_nick(guild, f"🗝️ {hunt.reversed_word}")
        st = dict(seed=seed, ends=time.time() + DURATION, spot=spot.id, spot_hint=[name[0], len(name)],
                  progress={}, finishers=[], channel=getattr(event_channel, "id", None), nick=clue_in_nick)
        self.store.meta_set(key(g), st)
        p = Panel("orange")
        p.title("La Chasse au trésor est ouverte !", icon="key",
                body=f"{E.scroll} **Quatre énigmes** sont cachées partout dans le serveur : un message chiffré, "
                     f"un parchemin caché dans un **autre salon**, un indice dans le **pseudo du bot**, une grille "
                     f"maudite.\n{E.crown} Le premier qui résout les quatre gagne **{config.fmt(PRIZES[0])}** "
                     f"{E.candy}, puis {config.fmt(PRIZES[1])} et {config.fmt(PRIZES[2])} ; chaque énigme résolue "
                     f"rapporte {STEP_PRIZE} {E.candy}.\n{E.hourglass} Fin {relative(st['ends'])}.\n"
                     f"**Tape `/tresor` pour recevoir ta première énigme !**")
        p.footer(f"{E.key} Les énigmes sont les mêmes pour tous : ne donnez pas les réponses dans le chat !")
        if event_channel is not None:
            try:
                await event_channel.send(view=panel_view(p), allowed_mentions=NO_PINGS)
            except discord.HTTPException:
                pass
        return None

    async def set_nick(self, guild, nick: str | None) -> bool:
        """The 3rd clue lives in the bot's nickname, which belongs to this server only."""
        me = getattr(guild, "me", None)
        try:
            await me.edit(nick=nick)
            return True
        except (discord.HTTPException, AttributeError, TypeError):
            LOG.debug("nickname change failed", exc_info=True)
            return False

    # ----------------------------------------------------------------- views
    def enigma(self, st, hunt, step: int):
        """(panel, files) for the player's current enigma."""
        info = T.STEPS[step]
        p = Panel("orange")
        files = []
        if step == 0:
            p.image(PNG[0])
            body = (f"Un esprit a chiffré un mot en décalant chaque lettre dans l'alphabet. La roue montre le "
                    f"décalage : la lettre **cyan** devient la lettre **rose**. Retrouve le mot d'origine "
                    f"({len(hunt.answers[0])} lettres).")
            files = [image_file(art.cipher_png(hunt.cipher_text, hunt.cipher_shift), PNG[0])]
        elif step == 1:
            first, n = st["spot_hint"]
            body = (f"Un parchemin a été **caché dans un salon du serveur**. Son nom commence par « **{first}** » "
                    f"et compte **{n}** caractères. Trouve-le, remets ses lettres dans l'ordre "
                    f"({len(hunt.answers[1])} lettres).")
        elif step == 2:
            if st.get("nick"):
                body = (f"Le bot murmure un mot… **regarde son pseudo** sur ce serveur (dans la liste des membres). "
                        f"Le mot y est écrit **à l'envers** ({len(hunt.answers[2])} lettres).")
            else:  # the bot could not rename itself: the clue is told here instead
                body = (f"Le bot murmure, à l'envers : **{hunt.reversed_word}**. Remets-le à l'endroit "
                        f"({len(hunt.answers[2])} lettres).")
        else:
            p.image(PNG[3])
            body = (f"Le mot final se cache dans la grille : il fait **{hunt.final_len}** lettres et commence par la "
                    f"dernière lettre de ta 3e réponse. Il peut se lire dans 5 directions.")
            files = [image_file(art.grid_png(hunt.grid, hunt.final_first, hunt.final_len), PNG[3])]
        p.title(f"Énigme {step + 1}/4 · {info['title']}", icon=info["icon"],
                body=body + "\n-# Réponds avec `/tresor reponse:` suivi du mot (sans accents, peu importe).")
        p.footer(f"{E.hourglass} Fin de la chasse {relative(st['ends'])} · {len(st['finishers'])} trésor(s) trouvé(s)")
        return p, files

    # -------------------------------------------------------------- commands
    @app_commands.command(name="tresor", description="🗝️ La Chasse au trésor du serveur : ton énigme, ou ta réponse")
    @app_commands.describe(reponse="Ta réponse à l'énigme en cours (laisse vide pour voir l'énigme)")
    @app_commands.guild_only()
    async def tresor(self, interaction: discord.Interaction, reponse: str | None = None):
        g, u = interaction.guild_id, interaction.user.id
        st = self.state(g)
        if not st:
            return await notice(interaction, "Aucune chasse au trésor en cours. Les organisateurs la lancent avec "
                                             "`/reglages lancer-chasse-tresor`.", icon="key", color="orange")
        hunt = T.make_hunt(st["seed"])
        step = st["progress"].get(str(u), 0)
        if step >= 4:
            rank = st["finishers"].index(u) + 1 if u in st["finishers"] else None
            return await notice(interaction, f"Tu as déjà trouvé le trésor{f' ({rank}e)' if rank else ''} ! "
                                             f"Patiente jusqu'à la fin de la chasse.", icon="crown", color="gold")
        if reponse is None:
            p, files = await asyncio.to_thread(self.enigma, st, hunt, step)
            return await interaction.response.send_message(view=panel_view(p), files=files, ephemeral=True)
        now = time.time()
        if now - self.wrong.get((g, u), 0) < WRONG_COOLDOWN:
            return await notice(interaction, "Doucement ! Attends quelques secondes entre deux réponses.")
        if not T.check(hunt, step, reponse):
            self.wrong[(g, u)] = now
            return await notice(interaction, f"« {reponse[:30]} »… ce n'est pas ça. Réessaie !")
        await self.solved(interaction, step)

    async def solved(self, interaction, step: int):
        g, u = interaction.guild_id, interaction.user.id
        async with self.lock:
            st = self.state(g)
            if not st or st["progress"].get(str(u), 0) != step:
                return await notice(interaction, "Cette énigme est déjà résolue.")
            st["progress"][str(u)] = step + 1
            rank = None
            if step == 3:
                st["finishers"].append(u)
                rank = len(st["finishers"])
            self.store.meta_set(key(g), st)
        stats = {"treasure_steps": 1}
        amount = STEP_PRIZE
        if rank is not None:
            amount += PRIZES[rank - 1] if rank <= len(PRIZES) else FINISH_PRIZE
            stats["treasure_found"] = 1
            if rank == 1:
                stats["treasure_win"] = 1
        r = grant(self.store, g, u, amount, 15 + 10 * step, "tresor", stats=stats)
        if rank is None:
            hunt = T.make_hunt(st["seed"])
            p, files = await asyncio.to_thread(self.enigma, st, hunt, step + 1)
            p.children.insert(0, discord.ui.TextDisplay(f"{E.check} **Bonne réponse !** {r.line()}"))
            return await interaction.response.send_message(view=panel_view(p), files=files, ephemeral=True)
        await notice(interaction, f"{E.crown} **TRÉSOR TROUVÉ !** Tu arrives **{rank}e**. {r.line()}",
                     icon="crown", color="gold")
        await self.announce(interaction.guild, interaction.user, rank, st)

    async def announce(self, guild, user, rank: int, st):
        channel = self.bot.get_channel(st["channel"]) if st.get("channel") else None
        if channel is None:
            return
        prize = PRIZES[rank - 1] if rank <= len(PRIZES) else FINISH_PRIZE
        p = Panel("gold")
        files = []
        if rank == 1:
            try:
                avatar = await avatar_bytes(user)
                data = await asyncio.to_thread(scenes.winner_clip, user.display_name, "TRÉSOR TROUVÉ !",
                                               f"+{config.fmt(prize)} BONBONS", "chest", neon.YELLOW, avatar,
                                               random.randrange(10**6))
                p.image("tresor.gif")
                files = [image_file(data, "tresor.gif")]
            except Exception:  # noqa: BLE001 - the announcement must go out anyway
                LOG.exception("treasure winner clip failed")
        p.title(f"{user.display_name} a trouvé le trésor !" if rank == 1 else f"{user.display_name} arrive {rank}e !",
                icon="crown" if rank == 1 else "medal1",
                body=f"{user.mention} a résolu les **4 énigmes** et gagne **{config.fmt(prize)}** {E.candy} !"
                     + ("\nLa chasse continue pour les places d'honneur… `/tresor`" if rank < len(PRIZES) else ""))
        try:
            await channel.send(view=panel_view(p), files=files, allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------- end
    async def end(self, guild, now: float | None = None) -> bool:
        g = guild.id
        st = self.state(g)
        if not st or st["ends"] > (now or time.time()):
            return False
        self.store.meta_del(key(g))
        hunt = T.make_hunt(st["seed"])
        if st.get("nick"):
            await self.set_nick(guild, None)
        channel = self.bot.get_channel(st["channel"]) if st.get("channel") else None
        if channel is None:
            return True
        shown = st["finishers"][:PODIUM_SHOWN]
        podium = "\n".join(f"{['🥇', '🥈', '🥉'][i] if i < 3 else '•'} <@{u}>" for i, u in enumerate(shown))
        if len(st["finishers"]) > PODIUM_SHOWN:
            podium += f"\n… et **{len(st['finishers']) - PODIUM_SHOWN}** autres chercheurs ont trouvé le trésor !"
        p = Panel("orange")
        p.title("Fin de la Chasse au trésor", icon="key",
                body=f"Les réponses étaient : **{'**, **'.join(hunt.answers)}**.\n"
                     + (podium if podium else "Personne n'a trouvé le trésor cette fois…"))
        try:
            await channel.send(view=panel_view(p), allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            pass
        return True

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
                await self.end(guild)
            except Exception:  # noqa: BLE001
                LOG.exception("treasure tick failed for %s", guild.id)


async def setup(bot):
    await bot.add_cog(Treasure(bot))
