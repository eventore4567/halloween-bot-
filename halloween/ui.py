"""The one and only panel format used by every command.

    ┌ accent colour ───────────────────────────────┐
    │ [animated GIF banner]                         │
    │ ## <icon> Title                    [thumbnail]│
    │ body…                                         │
    │ ───────────────────────────────────────────── │
    │ sections…                                     │
    │ ───────────────────────────────────────────── │
    │ [buttons / menus]                             │
    │ -# @player · balance · hint                   │
    └───────────────────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import re
from io import BytesIO
from typing import Awaitable, Callable

import discord

from . import config
from .art import banners, scroller
from .emojis import E

LOG = logging.getLogger(__name__)
NO_PINGS = discord.AllowedMentions.none()
STYLE = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "blurple": discord.ButtonStyle.primary,
    "grey": discord.ButtonStyle.secondary,
    "green": discord.ButtonStyle.success,
    "red": discord.ButtonStyle.danger,
}

Callback = Callable[[discord.Interaction], Awaitable[None]]

# Small caps line printed above every title ("◆ LE GRAND FRISSON"), set by the view being drawn.
KICKER: contextvars.ContextVar[str | None] = contextvars.ContextVar("kicker", default=None)


async def banner_file(key: str, **fmt) -> discord.File:
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, lambda: banners.banner_bytes(key, **fmt))
    return discord.File(BytesIO(data), filename=banners.banner_filename(key))


SCENE = "scene.gif"
ACTION = "action.gif"
MONSTERS = {"ghost", "bat", "vampire", "werewolf", "skull", "skull_fire", "reaper", "pumpkin_angry", "spider",
            "witch", "zombie", "mummy", "demon", "eye", "frog", "hunter"}


def cutscene_for(key: str, reward, seed: int = 0) -> bytes:
    """2D cutscene for the end of a game: the hero beats the game's monster (or gets knocked out)."""
    theme = banners.THEMES.get(key) or banners.THEMES["hub"]
    monster = next((i for i in (theme.right, theme.left) if i in MONSTERS), "ghost")
    color = theme.color2 if monster == theme.right else theme.color
    won = reward.candies > 0
    sub = ""
    if getattr(reward, "leveled", False):
        sub = f"NIVEAU {reward.new_level} !"
    elif reward.achievements:
        sub = f"SUCCÈS : {reward.achievements[0][1].upper()}"
    elif reward.xp:
        sub = f"+{reward.xp} XP"
    head = f"+{config.fmt(reward.candies)} BONBONS" if won else "PERDU…"
    return scroller.cutscene_gif(monster, color, won, reward.candies, head, sub, seed)


def image_file(data: bytes, filename: str) -> discord.File:
    return discord.File(BytesIO(data), filename=filename)


def button(label: str | None = None, emoji: str | None = None, style="secondary", callback: Callback | None = None,
           disabled=False, url: str | None = None) -> discord.ui.Button:
    b = discord.ui.Button(label=label, emoji=E.partial(emoji) if emoji else None,
                          style=discord.ButtonStyle.link if url else STYLE.get(style, style),
                          disabled=disabled, url=url)
    if callback and not url:
        b.callback = callback
    return b


class Panel:
    """Builder producing a single Components V2 container."""

    def __init__(self, color: int | str = "orange"):
        self.color = config.COLORS.get(color, color) if isinstance(color, str) else color
        self.children: list[discord.ui.Item] = []
        self.files: list[discord.File] = []

    # media --------------------------------------------------------------
    def banner(self, key: str):
        self.children.append(discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=f"attachment://{banners.banner_filename(key)}")))
        return self

    def image(self, filename: str):
        self.children.append(discord.ui.MediaGallery(discord.MediaGalleryItem(media=f"attachment://{filename}")))
        return self

    # text ---------------------------------------------------------------
    def title(self, title: str, body: str = "", icon: str | None = None, thumb: str | None = None):
        kicker = KICKER.get()
        top = f"-# {E(icon) + ' ' if icon else ''}{kicker or 'NUIT HANTÉE'}"
        head = f"{top}\n## {title}"
        content = head + ("\n" + body if body else "")
        if thumb:
            item = discord.ui.Section(discord.ui.TextDisplay(content), accessory=discord.ui.Thumbnail(media=thumb))
        else:
            item = discord.ui.TextDisplay(content)
        item._nh_title = True
        self.children.append(item)
        return self

    def text(self, content: str, thumb: str | None = None, accessory: discord.ui.Item | None = None):
        if not content:
            return self
        if thumb or accessory:
            acc = accessory or discord.ui.Thumbnail(media=thumb)
            self.children.append(discord.ui.Section(discord.ui.TextDisplay(content), accessory=acc))
        else:
            self.children.append(discord.ui.TextDisplay(content))
        return self

    def sep(self, visible=False, large=True):
        self.children.append(discord.ui.Separator(
            visible=visible, spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small))
        return self

    def row(self, *items: discord.ui.Item):
        items = [i for i in items if i is not None]
        if items:
            self.children.append(discord.ui.ActionRow(*items))
        return self

    def rows(self, items, per_row=5):
        items = list(items)
        for i in range(0, len(items), per_row):
            self.row(*items[i:i + per_row])
        return self

    def footer(self, text: str):
        """The player HUD. Whatever the call order, it is shown right under the banner."""
        self.hud = discord.ui.TextDisplay(text)
        return self

    def container(self) -> discord.ui.Container:
        children = list(self.children)
        # Signature layout: the title comes first, the animated scene right under it.
        if (len(children) > 1 and isinstance(children[0], discord.ui.MediaGallery)
                and getattr(children[1], "_nh_title", False)):
            children[0], children[1] = children[1], children[0]
        hud = getattr(self, "hud", None)
        if hud is not None:
            gallery = next((i for i, c in enumerate(children[:2]) if isinstance(c, discord.ui.MediaGallery)), None)
            children.insert(gallery + 1 if gallery is not None else 0, hud)
        return discord.ui.Container(*children)


def footer_for(store, guild_id: int, user: discord.abc.User, hint: str = "") -> str:
    """HUD line: balance, level and active boosts, in the bot's own ┃ style."""
    p = store.player(guild_id, user.id)
    level = config.level_from_xp(p["xp"])[0]
    parts = [f"{E.candy} **{config.fmt(p['candies'])}**", f"{E.star} niv. **{level}**"]
    if store.effect_active(guild_id, user.id, "luck"):
        parts.append(f"{E.potion_gold} gains **×2**")
    if store.effect_active(guild_id, user.id, "wisdom"):
        parts.append(f"{E.potion_green} XP **×2**")
    if hint:
        parts.append(hint)
    return "  ┃  ".join(parts)


class GameView(discord.ui.LayoutView):
    """A view owned by one player, fully re-rendered on every change."""

    owner_hint = "Lance ta propre partie avec la commande."

    def __init__(self, bot, interaction: discord.Interaction, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.store = bot.store
        self.guild_id = interaction.guild_id
        self.user = interaction.user
        self.owner_id = interaction.user.id
        self.message: discord.Message | None = None
        self.lock = asyncio.Lock()
        self.finished = False

    # to override -----------------------------------------------------------
    def build(self) -> Panel:
        raise NotImplementedError

    # helpers ---------------------------------------------------------------
    kicker: str | None = None

    def render(self):
        self.clear_items()
        token = KICKER.set(self.kicker)
        try:
            panel = self.build()
        finally:
            KICKER.reset(token)
        banner = f"attachment://{banners.banner_filename(self.banner_key)}" if self.banner_key else None
        self._shows_banner = False
        for i, child in enumerate(panel.children):
            if isinstance(child, discord.ui.MediaGallery) and banner and any(it.media.url == banner for it in child.items):
                self._shows_banner = True
                # the end-of-game cutscene, or the clip of the last action, replaces the banner
                name = SCENE if getattr(self, "_scene_ready", False) else getattr(self, "_action", None)
                if name:
                    panel.children[i] = discord.ui.MediaGallery(discord.MediaGalleryItem(media=f"attachment://{name}"))
        self.add_item(panel.container())

    # end-of-game cutscene ------------------------------------------------------
    cutscene = True  # set to False in a game that draws its own ending

    def _wants_scene(self, attachments) -> bool:
        reward = getattr(self, "reward", None)
        return (self.cutscene and attachments is None and getattr(self, "finished", False)
                and not getattr(self, "_scene_ready", False) and getattr(self, "_shows_banner", False)
                and hasattr(reward, "candies") and hasattr(reward, "achievements"))

    async def play_action(self, interaction, make, *args):
        """Show a short 2D clip of the action that was just played, in place of the banner."""
        try:
            data = await asyncio.to_thread(make, *args)
        except Exception:  # noqa: BLE001 - a clip must never break the game
            LOG.exception("action clip failed")
            return await self.refresh(interaction)
        self._action = ACTION
        await self.refresh(interaction, attachments=[image_file(data, ACTION)])

    async def _scene(self, attachments):
        """Render once; when the game just ended on its banner, swap in a 2D cutscene."""
        self.render()
        if not self._wants_scene(attachments):
            return attachments
        try:
            data = await asyncio.to_thread(cutscene_for, self.banner_key, self.reward, self.owner_id)
        except Exception:  # noqa: BLE001 - a cutscene must never break the game
            LOG.exception("cutscene failed")
            return attachments
        self._scene_ready = True
        self.render()
        return [image_file(data, SCENE)]

    def footer(self, hint=""):
        return footer_for(self.store, self.guild_id, self.user, hint)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await notice(interaction, f"Ce panneau appartient à {self.user.mention}. {self.owner_hint}")
            return False
        return True

    async def refresh(self, interaction: discord.Interaction, attachments=None):
        attachments = await self._scene(attachments)
        kwargs = dict(view=self, allowed_mentions=NO_PINGS)
        if attachments is not None:
            kwargs["attachments"] = attachments
        if interaction.response.is_done():
            msg = await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)
            msg = interaction.message
        if msg is not None:
            self.message = stable_message(msg)

    async def push(self, attachments=None):
        """Edit the message outside of an interaction (timers, animations)."""
        if not self.message:
            return
        attachments = await self._scene(attachments)
        kwargs = dict(view=self, allowed_mentions=NO_PINGS)
        if attachments is not None:
            kwargs["attachments"] = attachments
        try:
            await self.message.edit(**kwargs)
        except discord.HTTPException as exc:
            LOG.debug("push failed: %s", exc)

    banner_key: str | None = None

    def banner_fmt(self) -> dict:
        return {}

    async def extra_files(self) -> list[discord.File]:
        return []

    async def start(self, interaction: discord.Interaction, edit=False):
        files = []
        if self.banner_key:
            files.append(await banner_file(self.banner_key, **self.banner_fmt()))
        files += await self.extra_files()
        self.render()
        await send_view(interaction, self, files, edit)

    def finish(self):
        self.finished = True
        self.stop()

    async def on_timeout(self):
        if self.finished or not self.message:
            return
        self.finished = True
        self.on_expire()
        self.render()
        for item in self.walk_children():
            if isinstance(item, (discord.ui.Button, discord.ui.Select)) and not isinstance(item, discord.ui.DynamicItem):
                if getattr(item, "url", None):
                    continue
                if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("nh:"):
                    continue
                item.disabled = True
        try:
            await self.message.edit(view=self, allowed_mentions=NO_PINGS)
        except discord.HTTPException:
            pass

    def on_expire(self):
        """Hook: update state before the expired panel is drawn."""

    async def on_error(self, interaction, error, item):
        LOG.exception("View error in %s", type(self).__name__, exc_info=error)
        try:
            await notice(interaction, "Le sort a raté… réessaie dans un instant.")
        except discord.HTTPException:
            pass


def stable_message(msg):
    """Interaction webhooks expire after 15 minutes; edit through the channel instead."""
    if isinstance(msg, (discord.InteractionMessage, discord.WebhookMessage)):
        channel = getattr(msg, "channel", None)
        if channel is not None and hasattr(channel, "get_partial_message"):
            return channel.get_partial_message(msg.id)
    return msg


async def send_view(interaction: discord.Interaction, view: discord.ui.LayoutView, files=(), edit=False):
    files = list(files)
    if edit and interaction.message is not None:
        kwargs = dict(view=view, attachments=files, allowed_mentions=NO_PINGS)
        if interaction.response.is_done():
            msg = await interaction.edit_original_response(**kwargs)
        else:
            await interaction.response.edit_message(**kwargs)
            msg = interaction.message
    else:
        if interaction.response.is_done():
            msg = await interaction.followup.send(view=view, files=files, allowed_mentions=NO_PINGS, wait=True)
        else:
            await interaction.response.send_message(view=view, files=files, allowed_mentions=NO_PINGS)
            msg = await interaction.original_response()
    msg = stable_message(msg)
    if hasattr(view, "message") and msg is not None:
        view.message = msg
    return msg


async def notice(interaction: discord.Interaction, text: str, icon="cross", color="red"):
    """Small private message in the same visual format."""
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(discord.ui.TextDisplay(f"{E(icon)} {text}"),
                                       accent_colour=config.COLORS.get(color, color)))
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True, allowed_mentions=NO_PINGS)
    else:
        await interaction.response.send_message(view=view, ephemeral=True, allowed_mentions=NO_PINGS)


# ---------------------------------------------------------------------------
# Persistent navigation buttons (keep working after a restart)
# ---------------------------------------------------------------------------

class NavButton(discord.ui.DynamicItem[discord.ui.Button], template=r"nh:go:(?P<game>[a-z0-9_]+):(?P<owner>\d+)"):
    def __init__(self, game: str, owner: int, label: str, emoji: str, style="secondary"):
        super().__init__(discord.ui.Button(
            label=label, emoji=E.partial(emoji), style=STYLE.get(style, style),
            custom_id=f"nh:go:{game}:{owner}"))
        self.game = game
        self.owner = owner

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        inst = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(inst, item)
        inst.game = match["game"]
        inst.owner = int(match["owner"])
        return inst

    async def callback(self, interaction: discord.Interaction):
        opener = interaction.client.openers.get(self.game)
        if not opener:
            return await notice(interaction, "Ce jeu n'existe plus.")
        await opener(interaction, edit=interaction.user.id == self.owner)


class _PinnedPatterns(dict):
    """discord.py forgets a DynamicItem class as soon as one view holding it is
    removed or re-rendered without it. Our navigation buttons live on many
    messages at once, so their pattern must never be dropped."""

    def __init__(self, pinned, *args):
        super().__init__(*args)
        self.pinned = set(pinned)

    def pop(self, key, *default):
        if key in self.pinned:
            return self.get(key, *default)
        return super().pop(key, *default)


def register_navigation(bot):
    bot.add_dynamic_items(NavButton)
    store = getattr(getattr(bot, "_connection", None), "_view_store", None)
    if store is not None and hasattr(store, "_dynamic_items"):
        pattern = NavButton.__discord_ui_compiled_template__
        store._dynamic_items = _PinnedPatterns({pattern}, store._dynamic_items)


def nav(game: str, owner: int, label: str, emoji: str, style="secondary") -> NavButton:
    return NavButton(game, owner, label, emoji, style)


def relative(ts: float) -> str:
    return f"<t:{int(ts)}:R>"


def guild_only(interaction: discord.Interaction) -> bool:
    return interaction.guild_id is not None
