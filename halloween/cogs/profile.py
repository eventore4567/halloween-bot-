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
        manor = s.manor(g, u)
        theme = config.CARD_THEMES.get(p["theme"], config.CARD_THEMES["orange"])
        small = [
            ("crystal", "Quiz", config.fmt(stats.get("quiz_right", 0))),
            ("gift", "Cartes", f"{len(s.cards(g, u))}/{len(CARDS)}"),
            ("fire", "Série", f"{p['streak']} j"),
            ("soul", "Âmes", config.short(manor["lifetime"])),
        ]
        rank_txt = f"{rank}e / {total}" if rank and rank > 1 else ("1er / %d" % total if rank == 1 else "—")
        av = await avatar_bytes(self.member)
        data = await asyncio.to_thread(
            art.profile_card, self.member.display_name, title_of(s, g, u, level), level, into, need,
            config.fmt(p["candies"]), rank_txt, small, av, theme["colors"])
        return [image_file(data, "profil.png")]

    def build(self) -> Panel:
        s, g, u = self.store, self.guild_id, self.member.id
        me = u == self.owner_id
        p = Panel("orange").image("profil.png")
        player = s.player(g, u)
        level, _, _ = config.level_from_xp(player["xp"])
        p.title(f"{'Ton profil' if me else 'Profil de ' + self.member.display_name}", icon="pumpkin_lit",
                body=f"{E.star} Niveau **{level}** · *{title_of(s, g, u, level)}* · "
                     f"{E.candy} **{config.fmt(player['candies'])}** en poche · "
                     f"**{config.fmt(player['earned'])}** gagnés au total · {E.trophy} "
                     f"**{sum(1 for t in s.owned(g, u) if t.startswith('ach:'))}/{len(config.ACHIEVEMENTS)}** succès")
        p.sep()
        # today's quotas
        wheel_left = s.cooldown_left(g, u, "wheel")
        daily_done = player["last_daily"] == config.today()
        lines = [
            f"{E.crystal} Quiz : **{s.counter(g, u, 'quiz')}/{s.limit_for(g, u, 'quiz')}** questions",
            f"{E.eye} Mémoire : **{s.counter(g, u, 'memory')}/{config.LIMITS['memory']}** · "
            f"{E.ghost} Chasse : **{s.counter(g, u, 'hunt')}/{config.LIMITS['hunt']}** · "
            f"{E.skull} Pendu : **{s.counter(g, u, 'hangman')}/{config.LIMITS['hangman']}**",
            f"{E.house} Maison : **{s.counter(g, u, 'house')}/{config.LIMITS['house']}** · "
            f"{E.witch} Course : **{s.counter(g, u, 'race')}/{config.LIMITS['race']}** · "
            f"{E.candle} Rituel : **{s.counter(g, u, 'ritual')}/{config.LIMITS['ritual']}** · "
            f"{E.lightning} Réflexe : **{s.counter(g, u, 'reflex')}/{config.LIMITS['reflex']}**",
            f"{E.cauldron} Potions : **{s.counter(g, u, 'cauldron')}/{config.LIMITS['cauldron']}** · "
            f"{E.book} Recettes trouvées : **{len(s.recipes_found(g, u))}/8**",
            f"{E.wheel} Roue : " + (f"prête dans {relative(time.time() + wheel_left)}" if wheel_left else "**prête !**")
            + f" · {E.chest} Coffre : " + ("**ouvert**" if daily_done else "**à ouvrir !**"),
            f"-# Tout revient à zéro {relative(config.next_midnight_ts())}",
        ]
        p.text(f"### {E.hourglass} Aujourd'hui\n" + "\n".join(lines))
        # effects & inventory
        eff = s.effects(g, u)
        items = s.items(g, u)
        fx = []
        if "luck" in eff:
            fx.append(f"{E.potion_gold} **Bonbons ×2** jusqu'à {relative(eff['luck'])}")
        if "wisdom" in eff:
            fx.append(f"{E.potion_green} **XP ×2** jusqu'à {relative(eff['wisdom'])}")
        bonus = s.counter(g, u, "quiz_bonus")
        if bonus:
            fx.append(f"{E.potion_blue} **+{bonus} questions** de quiz aujourd'hui")
        inv_names = {"joker": ("joker", "Joker"), "shield": ("shield", "Bouclier"), "ticket": ("wheel", "Ticket de roue"),
                     "booster": ("gift", "Booster"), "amulet": ("gem", "Amulette")}
        inv = [f"{E(icon)} {name} ×**{items[k]}**" for k, (icon, name) in inv_names.items() if items.get(k)]
        if fx or inv:
            p.sep()
            p.text("### Effets & objets\n" + "\n".join(fx + ([" · ".join(inv)] if inv else [])))
        # manor
        manor = s.manor(g, u)
        rate = s.manor_rate(manor["units"])
        mrank, mtotal = s.rank(g, u, "manor")
        p.sep()
        p.text(f"### {E.soul} Manoir\n"
               f"**{config.short(manor['souls'])}** âmes en réserve · **{config.short(rate)}**/min · "
               + (f"Seigneur **#{mrank}** sur {mtotal}" if mrank else "pas encore classé"))
        p.sep()
        o = self.owner_id
        p.row(nav("quiz", o, "Quiz", "crystal"), nav("manor", o, "Manoir", "soul"),
              nav("cauldron", o, "Chaudron", "cauldron"), nav("wheel", o, "Roue", "wheel"),
              nav("house", o, "Maison", "house"))
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
