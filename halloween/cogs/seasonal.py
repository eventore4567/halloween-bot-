"""/calendrier (one box a day in October) and /citrouille (server giant pumpkin)."""
from __future__ import annotations

import asyncio
import datetime as dt
import random

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import seasonal as art
from ..content.games import CARDS
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

CAL_FILE, GIANT_FILE = "calendrier.png", "citrouille.png"


def october_day(now: dt.datetime | None = None) -> tuple[int, int | None]:
    """(year, day of October) or (year, None) outside October."""
    now = (now or dt.datetime.now(config.TZ)).astimezone(config.TZ)
    return now.year, (now.day if now.month == 10 else None)


def first_weekday(year: int) -> int:
    return dt.date(year, 10, 1).weekday()


class CalendarView(GameView):
    kicker = "CALENDRIER D'OCTOBRE"
    owner_hint = "Ouvre ton propre calendrier avec /calendrier."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.year, self.day = october_day()
        self.result = ""

    def opened(self) -> set[int]:
        prefix = f"cal:{self.year}-"
        return {int(t[len(prefix):]) for t in self.store.owned(self.guild_id, self.owner_id) if t.startswith(prefix)}

    async def extra_files(self):
        return [await self._picture()]

    async def _picture(self):
        emojis = {d: config.calendar_reward(d)["emoji"] for d in range(1, 32)}
        data = await asyncio.to_thread(art.calendar_png, self.opened(), self.day, emojis, first_weekday(self.year))
        return image_file(data, CAL_FILE)

    def build(self) -> Panel:
        p = Panel("orange").image(CAL_FILE)
        opened = self.opened()
        if self.day is None:
            p.title("Le calendrier dort", icon="lock",
                    body=f"Il ne s'ouvre qu'en **octobre**. Tu as ouvert **{len(opened)}/31** cases cette année.")
        else:
            today_open = self.day in opened
            reward = config.calendar_reward(self.day)
            body = (f"Case du **{self.day} octobre** : {E(reward['emoji'])} *{reward['label']}*\n" if not today_open
                    else f"{E.check} La case du jour est ouverte. La suivante s'ouvre {relative(config.next_midnight_ts())}.\n")
            body += f"-# {len(opened)}/31 cases ouvertes · le **31 octobre** cache le grand jackpot et une carte légendaire"
            p.title(f"{31 - self.day} nuit{'s' if 31 - self.day > 1 else ''} avant Halloween" if self.day < 31
                    else "C'EST HALLOWEEN !", icon="pumpkin_lit", body=(self.result + "\n\n" if self.result else "") + body)
            p.row(button("Ouvrir la case du jour", "gift", "success", self._open, disabled=today_open),
                  nav("daily", self.owner_id, "Coffre du jour", "chest"),
                  nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _open(self, interaction):
        async with self.lock:
            g, u = self.guild_id, self.owner_id
            if self.day is None or not self.store.unlock(g, u, f"cal:{self.year}-{self.day:02d}"):
                return await interaction.response.defer()
            await interaction.response.defer()
            reward = config.calendar_reward(self.day)
            extra = []
            candies = reward["candies"]
            if reward.get("cursed"):
                if random.random() < 0.5:
                    candies = 666
                    extra.append(f"{E.skull_fire} La malédiction t'est favorable : **666** bonbons !")
                else:
                    extra.append(f"{E.skull_fire} La case maudite était… vide. Hé hé hé.")
            if reward.get("item"):
                self.store.give_item(g, u, reward["item"])
                extra.append(f"{E(config.SHOP[reward['item']]['emoji'])} **{config.SHOP[reward['item']]['name']}** dans ton sac !")
            if reward.get("legendary"):
                card = random.choice([c for c in CARDS if c["rarity"] == "L"])
                self.store.add_card(g, u, card["key"])
                extra.append(f"{E(card['emoji'])} Carte légendaire : **{card['name']}** !")
            r = grant(self.store, g, u, candies, reward["xp"], "calendrier", stats={"calendar": 1})
            self.result = f"### {E.sparkle} Case du {self.day} octobre\n" + "\n".join(extra + [r.line()])
            await self.refresh(interaction, attachments=[await self._picture()])


class GiantView(GameView):
    kicker = "LA CITROUILLE GÉANTE"
    owner_hint = "Nourris la citrouille avec /citrouille."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=300)
        self.flash = ""

    async def interaction_check(self, interaction):
        return True  # the whole server feeds the same pumpkin

    @property
    def key(self):
        return f"giant:{self.guild_id}:{dt.datetime.now(config.TZ).year}"

    def state(self) -> dict:
        return self.store.meta_get(self.key, {"total": 0, "feeders": {}})

    async def extra_files(self):
        return [await self._picture()]

    async def _picture(self):
        st = self.state()
        total = st["total"]
        top = sorted(st["feeders"].items(), key=lambda kv: -kv[1])[:5]
        names = []
        guild = self.bot.get_guild(self.guild_id)
        for uid, amount in top:
            member = guild.get_member(int(uid)) if guild else None
            names.append((member.display_name if member else f"Joueur {str(uid)[-4:]}", amount))
        data = await asyncio.to_thread(art.giant_png, total, config.pumpkin_stage(total), config.PUMPKIN_STAGES, names)
        return image_file(data, GIANT_FILE)

    def build(self) -> Panel:
        st = self.state()
        stage = config.pumpkin_stage(st["total"])
        mine = st["feeders"].get(str(self.user.id), 0)
        p = Panel("orange").image(GIANT_FILE)
        nxt = config.PUMPKIN_STAGES[stage + 1][0] if stage + 1 < len(config.PUMPKIN_STAGES) else None
        p.title(config.PUMPKIN_STAGES[stage][1], icon="pumpkin_lit",
                body=(self.flash + "\n\n" if self.flash else "")
                + "Tout le serveur nourrit **la même citrouille** avec ses bonbons. À chaque nouvelle étape, "
                  "**chaque jardinier** reçoit une récompense selon ce qu'il a donné.\n"
                + (f"{E.bar(st['total'] - config.PUMPKIN_STAGES[stage][0], nxt - config.PUMPKIN_STAGES[stage][0], 8)} "
                   f"encore **{config.fmt(nxt - st['total'])}** {E.candy} avant l'étape suivante" if nxt
                   else f"{E.crown} Elle a atteint sa taille maximale !")
                + f"\n-# Tu as donné **{config.fmt(mine)}** {E.candy} à la citrouille cette année.")
        p.row(*[button(f"Donner {amount}", "candy", "success" if i == 0 else "primary", self._feed(amount))
                for i, amount in enumerate(config.PUMPKIN_FEEDS)],
              nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    def _feed(self, amount):
        async def cb(interaction):
            uid = interaction.user.id
            g = self.guild_id
            try:
                self.store.spend(g, uid, amount, "citrouille")
            except NotEnough:
                from ..ui import notice
                return await notice(interaction, f"Il te faut **{amount}** bonbons pour nourrir la citrouille.")
            await interaction.response.defer()
            async with self.lock:
                st = self.state()
                before = config.pumpkin_stage(st["total"])
                st["total"] += amount
                st["feeders"][str(uid)] = st["feeders"].get(str(uid), 0) + amount
                self.store.meta_set(self.key, st)
                after = config.pumpkin_stage(st["total"])
                r = grant(self.store, g, uid, 0, max(1, amount // 25), "citrouille", stats={"pumpkin_fed": amount})
                self.flash = f"{E.candy} **{interaction.user.display_name}** donne **{amount}** bonbons à la citrouille !"
                if r.achievements or r.leveled:
                    self.flash += "\n" + r.line()
                if after > before:
                    paid = 0
                    for feeder, given in st["feeders"].items():
                        bonus = int(given * 0.12) + 40 * after
                        grant(self.store, g, int(feeder), bonus, 20 * after, "citrouille-etape")
                        paid += 1
                    self.flash += (f"\n### {E.sparkle} LA CITROUILLE GRANDIT : {config.PUMPKIN_STAGES[after][1]} !\n"
                                   f"{paid} jardinier{'s' if paid > 1 else ''} reçoivent leur récompense "
                                   f"(12 % de leurs dons + {40 * after} {E.candy}) !")
                await self.refresh(interaction, attachments=[await self._picture()])
        return cb


class Seasonal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["calendar"] = self.open_calendar
        bot.openers["giant"] = self.open_giant

    async def open_calendar(self, interaction, edit=False):
        await interaction.response.defer(thinking=not edit)
        await CalendarView(self.bot, interaction).start(interaction, edit)

    async def open_giant(self, interaction, edit=False):
        await interaction.response.defer(thinking=not edit)
        await GiantView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="calendrier", description="🎁 Le calendrier d'octobre : une case à ouvrir chaque jour jusqu'à Halloween")
    @app_commands.guild_only()
    async def calendrier(self, interaction: discord.Interaction):
        await self.open_calendar(interaction)

    @app_commands.command(name="citrouille", description="🎃 La citrouille géante du serveur : nourris-la tous ensemble")
    @app_commands.guild_only()
    async def citrouille(self, interaction: discord.Interaction):
        await self.open_giant(interaction)


async def setup(bot):
    await bot.add_cog(Seasonal(bot))
