"""/profil — generated player card + daily quotas + quick launch buttons."""
from __future__ import annotations

import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import cards as art
from ..content.games import CARDS
from ..emojis import E
from ..ui import GameView, Panel, image_file, nav, relative


async def avatar_bytes(user: discord.abc.User) -> bytes | None:
    try:
        return await user.display_avatar.replace(size=256, static_format="png").read()
    except (discord.HTTPException, discord.NotFound, ValueError):
        return None


def title_of(store, g, u, level) -> str:
    p = store.player(g, u)
    if p["title"]:
        from ..config import TITLES_SHOP
        if p["title"] in TITLES_SHOP:
            return TITLES_SHOP[p["title"]]["name"]
    return config.rank_title(level)


class ProfileView(GameView):
    kicker = "PROFIL"
    def __init__(self, bot, interaction, member: discord.abc.User):
        super().__init__(bot, interaction, timeout=600)
        self.member = member

    async def interaction_check(self, interaction):
        return True

    async def extra_files(self):
        s, g, u = self.store, self.guild_id, self.member.id
        p = s.player(g, u)
        level, into, need = config.level_from_xp(p["xp"])
        rank, total = s.rank(g, u, "candies")
        stats = s.stats(g, u)
        theme = config.CARD_THEMES.get(p["theme"], config.CARD_THEMES["orange"])
        small = [
            ("skull", "Frisson", f"{stats.get('show_best', 0)}/12"),
            ("gift", "Cartes", f"{len(s.cards(g, u))}/{len(CARDS)}"),
            ("fire", "Série", f"{p['streak']} j"),
            ("key", "Missions", config.fmt(stats.get("exp_win", 0))),
        ]
        rank_txt = f"{rank}e / {total}" if rank and rank > 1 else ("1er / %d" % total if rank == 1 else "—")
        av = await avatar_bytes(self.member)
        data = await asyncio.to_thread(
            art.profile_card, self.member.display_name, title_of(s, g, u, level), level, into, need,
            config.fmt(p["candies"]), rank_txt, small, av, theme["colors"])
        return [image_file(data, "profil.png")]

    def _night_grid(self):
        """Compact grid of tonight's plays: every game with what is left."""
        s, g, u = self.store, self.guild_id, self.member.id
        cells = [("skull", "Frisson", "quiz"), ("house", "Maison", "house"), ("witch", "Course", "race"),
                 ("cauldron", "Formule", "cauldron"), ("eye", "Mémoire", "memory"), ("ghost", "Chasse", "hunt"),
                 ("bone", "Pendu", "hangman"), ("candle", "Rituel", "ritual"), ("lightning", "Réflexe", "reflex")]
        out = []
        for icon, name, key in cells:
            left = s.remaining(g, u, key)
            out.append(f"{E(icon)} {name} **{left}**" if left else f"{E.lock} ~~{name}~~")
        rows = [" ┃ ".join(out[i:i + 3]) for i in range(0, len(out), 3)]
        wheel_left = s.cooldown_left(g, u, "wheel")
        daily_done = s.player(g, u)["last_daily"] == config.today()
        extra = (f"{E.wheel} Roue " + (f"{relative(time.time() + wheel_left)}" if wheel_left else "**prête**")
                 + f" ┃ {E.chest} Coffre " + ("~~ouvert~~" if daily_done else "**à ouvrir**"))
        return "\n".join(rows + [extra])

    def build(self) -> Panel:
        s, g, u = self.store, self.guild_id, self.member.id
        me = u == self.owner_id
        p = Panel("orange").image("profil.png")
        player = s.player(g, u)
        level, _, _ = config.level_from_xp(player["xp"])
        trophies = sum(1 for t in s.owned(g, u) if t.startswith("ach:"))
        p.title(self.member.display_name if not me else "Ta carte de chasseur", icon="pumpkin_lit",
                body=f"*{title_of(s, g, u, level)}* · **{config.fmt(player['earned'])}** {E.candy} gagnés depuis le "
                     f"début · {E.trophy} **{trophies}/{len(config.ACHIEVEMENTS)}** succès")
        p.sep()
        p.text(f"**{E.moon} Parties restantes ce soir**\n{self._night_grid()}\n"
               f"-# Nouvelle nuit {relative(config.next_midnight_ts())}")
        eff = s.effects(g, u)
        items = s.items(g, u)
        bag = []
        if "luck" in eff:
            bag.append(f"{E.potion_gold} gains ×2 → {relative(eff['luck'])}")
        if "wisdom" in eff:
            bag.append(f"{E.potion_green} XP ×2 → {relative(eff['wisdom'])}")
        names = {"joker": ("joker", "joker"), "shield": ("shield", "bouclier"), "ticket": ("wheel", "ticket"),
                 "booster": ("gift", "booster"), "amulet": ("gem", "amulette")}
        bag += [f"{E(icon)} {items[k]} {name}{'s' if items[k] > 1 else ''}" for k, (icon, name) in names.items()
                if items.get(k)]
        trip = s.meta_get(f"exp:{g}:{u}")
        if trip:
            bag.append(f"{E.key} expédition : retour {relative(trip['ends'])}")
        if bag:
            p.sep()
            p.text(f"**{E.candy_bag} Dans le sac**\n" + " ┃ ".join(bag))
        p.sep()
        o = self.owner_id
        p.row(nav("quiz", o, "Grand Frisson", "skull"), nav("house", o, "Maison", "house"),
              nav("manor", o, "Expédition", "key"), nav("cauldron", o, "Formule", "cauldron"),
              nav("wheel", o, "Roue", "wheel"))
        p.row(nav("cards", o, "Cartes", "gift"), nav("shop", o, "Boutique", "witch"),
              nav("top", o, "Classement", "trophy"), nav("trophies", o, "Succès", "medal1"),
              nav("hub", o, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["profile"] = self.open

    async def open(self, interaction, edit=False, member=None):
        await interaction.response.defer(thinking=not edit)
        view = ProfileView(self.bot, interaction, member or interaction.user)
        await view.start(interaction, edit)

    @app_commands.command(name="profil", description="🎃 Ta carte de chasseur, tes quotas et tes effets")
    @app_commands.describe(membre="Voir le profil de quelqu'un d'autre")
    @app_commands.guild_only()
    async def profil(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        if membre and membre.bot:
            membre = None
        await self.open(interaction, member=membre)


async def setup(bot):
    await bot.add_cog(Profile(bot))
