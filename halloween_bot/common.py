"""Halloween theme: polished Discord panels and application-owned emojis.

When the bot has application emojis named pumpkin, candy, ghost etc., those
automatically replace Unicode icons in embeds, buttons and select menus.
No emojis need to be added to any server.
"""
from __future__ import annotations
import logging
import re
import time

import discord

LOG = logging.getLogger(__name__)

COLORS = {
    "pumpkin": 0xF39A36,
    "night": 0x6E4BC5,
    "ghost": 0x40B5AC,
    "danger": 0xDF5265,
    "success": 0x51B991,
    "gold": 0xF4C565,
}
FALLBACK = {
    "pumpkin": "🎃",
    "candy": "🍬",
    "ghost": "👻",
    "bat": "🦇",
    "skull": "💀",
    "web": "🕸️",
    "spider": "🕷️",
    "moon": "🌙",
    "lantern": "🏮",
    "candle": "🕯️",
    "trophy": "🏆",
    "shop": "🛒",
    "bag": "🎒",
    "gift": "🎁",
    "garden": "🌾",
    "house": "🏚️",
    "duel": "⚔️",
    "quiz": "🧩",
    "sparkle": "✨",
    "crown": "👑",
    "wand": "🪄",
    "check": "✅",
    "cross": "❌",
    "lock": "🔒",
    "clock": "⏳",
    "seed": "🌱",
    "key": "🗝️",
    "star": "⭐",
    "heart": "❤️",
    "gem": "💎",
    "hat": "🧙",
    "broom": "🧹",
    "map": "🗺️",
    "gear": "⚙️",
    "fire": "🔥",
    "book": "📜",
    "sword": "🗡️",
    "shield": "🛡️",
}
ALIASES = {
    "pumpkin": ("citrouille", "halloween_pumpkin"),
    "candy": ("bonbon", "bonbons", "halloween_candy"),
    "ghost": ("fantome", "halloween_ghost"),
    "bat": ("chauvesouris", "halloween_bat"),
    "skull": ("tete_de_mort", "halloween_skull"),
    "web": ("toile", "halloween_web"),
    "trophy": ("classement",),
    "garden": ("farm", "ferme"),
    "shop": ("boutique",),
    "bag": ("inventaire",),
}
TITLE_ICONS = (
    (("classement", "top 10", "leaderboard", "rang", "cup", "compétition", "tournoi", "saison", "défi remporté"), "trophy"),
    (("boutique", "achat"), "shop"),
    (("inventaire", "collection"), "bag"),
    (("profil",), "pumpkin"),
    (("succès", "achievements"), "trophy"),
    (("potager", "ferme", "récolte"), "garden"),
    (("fantôme", "spectre", "chasse"), "ghost"),
    (("duel", "défi"), "duel"),
    (("boss", "roi des citrouilles"), "skull"),
    (("énigme", "quiz"), "quiz"),
    (("maison", "expédition", "exploration"), "house"),
    (("cadeau",), "gift"),
    (("configuration",), "gear"),
    (("événement", "apparition"), "bat"),
    (("citrouille",), "pumpkin"),
    (("bonbon", "panier", "trick"), "candy"),
    (("guide",), "book"),
)
BRAND = "HALLOWEEN  •  LE ROYAUME HANTÉ"
FOOTER = "Le royaume hanté  •  Jouez, récoltez, collectionnez"


class IconPack:
    """Application emoji cache with a safe Unicode fallback."""

    def __init__(self):
        self.by_key = {}
        self.avatar_url = None
        self._patterns = sorted(
            ((symbol, name) for name, symbol in FALLBACK.items()),
            key=lambda pair: len(pair[0]), reverse=True
        )

    def install(self, emojis, bot_user=None):
        names = {em.name.lower(): em for em in emojis if getattr(em, "name", None)}
        self.by_key.clear()
        for key in FALLBACK:
            for name in (key, "halloween_" + key, *ALIASES.get(key, ())):
                if name in names:
                    self.by_key[key] = names[name]
                    break
        if bot_user:
            self.avatar_url = str(bot_user.display_avatar.url)
        LOG.info("Halloween emoji pack: %s custom icons", len(self.by_key))

    def icon(self, key):
        emoji = self.by_key.get(key)
        return str(emoji) if emoji else FALLBACK.get(key, "🎃")

    def button(self, key):
        return self.by_key.get(key) or FALLBACK.get(key, "🎃")

    def replace(self, text):
        text = str(text)
        if not self.by_key:
            return text
        substitutions = {
            symbol: str(self.by_key[key])
            for symbol, key in self._patterns if key in self.by_key
        }
        if not substitutions:
            return text
        regex = re.compile("|".join(re.escape(x) for x in substitutions))
        return regex.sub(lambda match: substitutions[match.group()], text)

    def decorate_view(self, view):
        for child in view.children:
            if isinstance(child, discord.ui.Button) and child.emoji:
                key = self.lookup(str(child.emoji))
                if key:
                    child.emoji = self.button(key)
            if isinstance(child, discord.ui.Select):
                for option in getattr(child, "options", []):
                    if option.emoji:
                        key = self.lookup(str(option.emoji))
                        if key:
                            option.emoji = self.button(key)
        return view

    @staticmethod
    def lookup(value):
        for key, emoji in FALLBACK.items():
            if value == emoji:
                return key
        return None


ICONS = IconPack()


async def load_application_emojis(bot):
    try:
        app_emojis = await bot.fetch_application_emojis()
    except (discord.HTTPException, discord.ClientException, AttributeError) as exc:
        LOG.warning("Application emojis unavailable, Unicode fallback: %s", exc)
        app_emojis = []
    ICONS.install(app_emojis, bot.user)


async def ensure_application_emojis(bot):
    """Publish only missing CRYPT CUP images to this bot's own application.

    The official discord.py create_application_emoji method writes through the
    application emoji REST API. New emojis appear under Developer Portal >
    Application > Emojis. Existing names are never overwritten or deleted.
    Safe to call on every Railway start; missing icons fall back to Unicode.
    """
    import asyncio
    from .emoji_art import EMOJI_NAMES, render_emoji

    try:
        existing = await bot.fetch_application_emojis()
    except (discord.HTTPException, discord.ClientException, AttributeError) as exc:
        LOG.warning("Cannot inspect application emojis; skipping upload: %s", exc)
        ICONS.install([], getattr(bot, "user", None))
        return {"created": [], "existing": [], "failed": list(EMOJI_NAMES)}

    by_name = {item.name.lower(): item for item in existing}
    created, failed = [], []
    for name in EMOJI_NAMES:
        if name in by_name:
            continue
        try:
            icon_bytes = render_emoji(name)
            emoji = await bot.create_application_emoji(name=name, image=icon_bytes)
        except (discord.HTTPException, discord.ClientException, AttributeError,
                ValueError, OSError) as exc:
            failed.append(name)
            LOG.warning("Cannot create application emoji %s: %s", name, exc)
            continue
        created.append(name)
        by_name[name] = emoji
        LOG.info("Created application emoji: %s", name)
        # Keep uploads gentle even if this is the first run on a fresh app.
        await asyncio.sleep(0.25)
    all_icons = list(by_name.values())
    # A new fetch ensures consistent objects and names for all UI modules.
    if created:
        try:
            all_icons = await bot.fetch_application_emojis()
        except discord.HTTPException as exc:
            LOG.warning("Emoji refresh failed; using returned emoji objects: %s", exc)
    ICONS.install(all_icons, getattr(bot, "user", None))
    LOG.info("App emoji bootstrap: %s created, %s already present, %s failed",
             len(created), len(EMOJI_NAMES) - len(created) - len(failed),
             len(failed))
    return {
        "created": created,
        "existing": [name for name in EMOJI_NAMES if name in by_name and name not in created],
        "failed": failed,
    }


def icon(name):
    return ICONS.icon(name)


def button_icon(name):
    return ICONS.button(name)


def pretty(text):
    return ICONS.replace(text)


def themed_view(view):
    return ICONS.decorate_view(view)


def _pick_icon(title):
    name = title.casefold()
    for terms, key in TITLE_ICONS:
        if any(term in name for term in terms):
            return key
    return "pumpkin"


def card(title, description="", *, purple=False, theme=None, sections=None,
         note=None, thumbnail=False):
    """Build a consistent themed embed, backwards-compatible with old calls."""
    if theme is None:
        theme = "night" if purple else "pumpkin"
    theme = theme if theme in COLORS else "pumpkin"
    title = str(title).strip()
    for symbol in FALLBACK.values():
        if title.startswith(symbol):
            title = title[len(symbol):].strip(" ・|-")
            break
    embed = discord.Embed(
        title=f"{icon(_pick_icon(title))}  {title}",
        description=pretty(description) if description else None,
        color=discord.Color(COLORS[theme]),
    )
    embed.set_author(name=BRAND, icon_url=ICONS.avatar_url)
    if thumbnail and ICONS.avatar_url:
        embed.set_thumbnail(url=ICONS.avatar_url)
    for section in sections or ():
        name, value, *inline = section
        embed.add_field(name=pretty(name), value=pretty(value) or "\u200b",
                        inline=inline[0] if inline else False)
    if note:
        embed.add_field(name=f"{icon('candle')}  À savoir", value=pretty(note),
                        inline=False)
    embed.set_footer(text=FOOTER, icon_url=ICONS.avatar_url)
    return embed


def progress(current, total, *, width=10):
    fraction = max(0, min(1, current / total)) if total else 0
    count = round(width * fraction)
    return "🟧" * count + "⬛" * (width - count)


def wait_text(seconds):
    return f"{icon('candle')} Disponible <t:{int(time.time()) + int(seconds)}:R>."


async def fail(interaction, message):
    text = pretty(f"💀 {message}")
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


def format_rank(guild, rows, emoji="🍬"):
    if not rows:
        return f"{icon('web')} Aucun joueur. Utilise /daily pour commencer."
    medals = ["🥇", "🥈", "🥉"]
    output = []
    for n, row in enumerate(rows, 1):
        member = guild.get_member(row["user_id"])
        name = (discord.utils.escape_markdown(member.display_name)
                if member else f"Joueur {row['user_id']}")
        medal = medals[n - 1] if n <= 3 else f"#{n:02}"
        output.append(f"{medal}  **{name}**\n"
                      f"　└ {row['score']:,} {emoji}")
    return pretty("\n\n".join(output))


class OwnerView(discord.ui.View):
    def __init__(self, owner_id, timeout=180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        themed_view(self)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await fail(interaction, "Ce panneau appartient à un autre joueur.")
            return False
        return True


def authorized(interaction):
    return (isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.manage_guild)
