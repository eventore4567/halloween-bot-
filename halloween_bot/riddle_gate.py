"""Shared Halloween puzzle gateway for interactive reward-bearing commands.

Unlike /trickortreat's dedicated scene, this gate can hand off to existing
Discord embed + View games by editing its OWN message. No new channels, no
ephemeral responses and no change to the quiz/arcade scoring systems.
"""
from __future__ import annotations

import asyncio
import logging
import random
import unicodedata
from io import BytesIO

import discord
from PIL import ImageDraw

from .common import card, fail
from .trick_or_treat import (
    DOOR_RIDDLES, _background, _fit, _font, _write,
    COPPER, CREAM, BRIGHT, LILAC, PERIL, MINT, WIDTH, HEIGHT,
    _visual_prize,
)

LOG = logging.getLogger(__name__)
FILENAME = "crypt-defi-halloween.jpg"


def make_gate_art(game, question):
    """A 16:9-ish, self-contained, Halloween illustration with readable text."""
    image=_background()
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((66, 43, 1206, 660), radius=26,
                           fill=(16, 11, 32, 244),
                           outline=(240, 151, 91, 220), width=4)
    _write(image, (110, 78), "CRYPT CUP   /   LE DÉFI HALLOWEEN", 24, LILAC)
    _write(image, (105, 136), game.upper(),
           _fit(game.upper(), 960, size=62, min_size=35), COPPER, glow=4)
    draw.line((106, 213, 1153, 213), fill=(226, 143, 107, 180), width=3)
    _write(image, (110, 244), "LE GARDIEN TE POSE UNE ÉNIGME", 27, BRIGHT)
    question=str(question)
    words=question.split()
    lines=[]
    candidate=""
    font=_font(35)
    ruler=ImageDraw.Draw(image)
    for word in words:
        joined=(candidate + " " + word).strip()
        if ruler.textbbox((0, 0), joined, font=font)[2]>985 and candidate:
            lines.append(candidate)
            candidate=word
        else:
            candidate=joined
    if candidate:
        lines.append(candidate)
    lines=lines[:3]
    d_height=max(60, len(lines)*63)
    top=348-(d_height-63)//2
    for n,line in enumerate(lines):
        _write(image, (630, top+n*66), line,
               _fit(line, 1020, size=35, min_size=22),
               CREAM, anchor="mm")
    draw.rounded_rectangle((124, 474, 1140, 543), radius=19,
                           fill=(49, 29, 65, 240),
                           outline=(180, 135, 226, 175), width=3)
    _write(image, (630, 495), "3 CHOIX  •  1 BONNE RÉPONSE",
           30, BRIGHT, anchor="mt")
    _write(image, (630, 594), "LES VRAIS BOUTONS SONT SOUS CETTE IMAGE",
           23, LILAC, anchor="mm")
    out=BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=87, optimize=True)
    return out.getvalue()


def make_reward_art(game, outcome, amount, note=""):
    """Distinct visual reward scene from the same CRYPT CUP art language."""
    if outcome not in ("treat","jackpot","trick","nothing"):
        raise ValueError("Unsupported Halloween reward illustration")
    image=_background()
    draw=ImageDraw.Draw(image)
    theme={
        "treat":MINT, "jackpot":BRIGHT, "trick":PERIL, "nothing":LILAC
    }[outcome]
    _write(image,(88,62),"CRYPT CUP   /   LE VERDICT HALLOWEEN",23,LILAC)
    title=game.upper()
    _write(image,(83,105),title,_fit(title,950,size=62,min_size=36),
           COPPER,glow=3)
    draw.rounded_rectangle((66,234,1206,586),radius=22,
                           fill=(16,11,31,231),outline=(*theme,208),width=4)
    _visual_prize(image,outcome)
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((568,259,1181,567),radius=22,
                           fill=(32,22,47,248),
                           outline=(*theme,170),width=3)
    amount_label=(f"+{amount}" if amount>0 else str(amount))+" BONBONS"
    _write(image,(602,297),"RÉCOMPENSE DU DÉFI",27,LILAC)
    _write(image,(591,356),amount_label,
           _fit(amount_label,555,size=48,min_size=28),theme,glow=3)
    draw.line((599,426,1151,426),fill=(*theme,150),width=2)
    # Vera supports French text, not pictographic emoji. Strip only art
    # pictographs; emoji remain intact in the native Discord embed.
    short="".join(c for c in note.strip().replace("\n"," ")
                  if unicodedata.category(c) not in ("So","Cf")
                  and c not in "\ufe0f")[:80].strip()
    short=short or "Le manoir a décidé de ton sort."
    # Keep result caption readable on desktop/mobile.
    words=short.split()
    parts=[]
    candidate=""
    measure=ImageDraw.Draw(image)
    for word in words:
        combo=(candidate+" "+word).strip()
        if measure.textbbox((0,0),combo,font=_font(24))[2]>530 and candidate:
            parts.append(candidate)
            candidate=word
        else:
            candidate=combo
    if candidate:
        parts.append(candidate)
    for index,line in enumerate(parts[:3]):
        _write(image,(604,458+index*33),line,
               _fit(line,520,size=24,min_size=18),CREAM)
    _write(image,(615,635),"PROCHAINE ÉTAPE : RELANCE LE JEU",
           21,BRIGHT)
    stream=BytesIO()
    image.convert("RGB").save(stream,"JPEG",quality=87,optimize=True)
    return stream.getvalue()


def reward_file(game,outcome,amount,note=""):
    return discord.File(
        BytesIO(make_reward_art(game,outcome,amount,note)),filename=FILENAME
    )


class RiddleGate(discord.ui.View):
    """One owner, three native buttons, one reward-bearing continuation.

    The continuation is run only once a correct answer is given. It must
    return (embed, replacement_view) or None after responding with a
    transient error; cooldowns are checked inside the continuation.
    """
    def __init__(self, game, owner_id, guild_id, continuation, *,
                 mention_user=None, timeout=110):
        super().__init__(timeout=timeout)
        self.game=game
        self.owner_id=owner_id
        self.guild_id=guild_id
        self.continuation=continuation
        self.mention_user=mention_user
        self.riddle=random.choice(DOOR_RIDDLES)
        self.attempts=0
        self.finished=False
        self.message=None
        self._lock=asyncio.Lock()
        for i,option in enumerate(self.riddle[1]):
            button=discord.ui.Button(
                label=f"{'ABC'[i]} · {option}"[:80],
                style=discord.ButtonStyle.primary if i==0
                      else discord.ButtonStyle.secondary,
            )
            async def handler(interaction, choice=i):
                await self.answer(interaction, choice)
            button.callback=handler
            self.add_item(button)

    def art(self):
        return discord.File(
            BytesIO(make_gate_art(self.game,self.riddle[0])),
            filename=FILENAME
        )

    def panel(self, *, wrong=False):
        details=(
            "❌ Mauvaise réponse. Le gardien attend une autre proposition."
            if wrong else
            "🧩 Choisis la bonne réponse pour déverrouiller le défi."
        )
        panel=card(
            f"Épreuve : {self.game}",
            f"**{self.riddle[0]}**\n\n{details}",
            theme="danger" if wrong else "night",
            sections=[
                ("🔐 DÉVERROUILLAGE", "3 réponses possibles · aucun bonbon consommé avant la réussite.", False),
            ],
        )
        panel.set_image(url=f"attachment://{FILENAME}")
        return panel

    async def interaction_check(self, interaction):
        if (not interaction.guild or interaction.guild.id!=self.guild_id
                or interaction.user.id!=self.owner_id
                or interaction.user.bot):
            await fail(interaction,
                       "Cette épreuve appartient à un autre joueur. Lance ta propre commande.")
            return False
        return True

    async def answer(self, interaction, choice):
        async with self._lock:
            if self.finished:
                return await fail(interaction,"Cette épreuve est déjà terminée.")
            if choice not in range(3):
                return await fail(interaction,"Ce choix n'existe pas.")
            if choice != self.riddle[2]:
                self.attempts+=1
                return await interaction.response.edit_message(
                    embed=self.panel(wrong=True),
                    view=self,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            # A callback checks and consumes the original game's cooldown
            # AFTER the riddle. Exactly one callback per gate instance.
            self.finished=True
            try:
                result=await self.continuation(interaction)
            except Exception:
                self.finished=False
                LOG.exception("Halloween riddle continuation failed for %s",self.game)
                return await fail(interaction,"Une erreur a empêché l'ouverture du jeu.")
            if result is None:
                # Usually a transient cooldown conflict with another panel.
                self.finished=False
                return
            embed, next_view = result[:2]
            new_art = result[2] if len(result)>2 else None
            if new_art is not None:
                embed.set_image(url=f"attachment://{FILENAME}")
            if next_view is not None and hasattr(next_view,"message"):
                next_view.message=interaction.message
            for btn in self.children:
                btn.disabled=True
            # Standard discord.ui.View is intentionally used here, not
            # LayoutView: it can hand off to the existing embed/view games.
            await interaction.response.edit_message(
                embed=embed,view=next_view,
                attachments=[new_art] if new_art is not None else [],
                allowed_mentions=(
                    discord.AllowedMentions(users=[self.mention_user],
                                            roles=False,everyone=False)
                    if self.mention_user is not None else
                    discord.AllowedMentions.none()
                ),
            )
            self.stop()

    async def on_timeout(self):
        async with self._lock:
            if self.finished:
                return
            self.finished=True
            for button in self.children:
                button.disabled=True
            if self.message is not None:
                try:
                    await self.message.edit(
                        embed=card("Épreuve expirée",
                                   "🌫️ Le gardien referme le passage. Relance la commande pour réessayer.",
                                   theme="night"),
                        view=self,attachments=[],
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.HTTPException,discord.NotFound):
                    LOG.debug("Expired Halloween gate message no longer available")


async def launch_gate(interaction, game, continuation, *, mention_user=None):
    """Send one public message and reuse it for riddle, game and outcome."""
    gate=RiddleGate(game,interaction.user.id,interaction.guild.id,
                    continuation,mention_user=mention_user)
    if getattr(interaction.app_permissions,"attach_files",False):
        await interaction.response.send_message(
            embed=gate.panel(),view=gate,file=gate.art(),
            ephemeral=False,allowed_mentions=discord.AllowedMentions.none(),
        )
    else:
        # Embeds and buttons still work without the Attach Files permission.
        panel=gate.panel()
        panel.set_image(url=None)
        await interaction.response.send_message(
            embed=panel,view=gate,ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    gate.message=await interaction.original_response()
