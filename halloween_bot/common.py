"""Reusable Discord visual components and permission helpers."""
import time
import discord
from .content import ORANGE, PURPLE

def card(title, description, *, purple=False):
    box = discord.Embed(title=f"🎃・{title}", description=description,
                        color=PURPLE if purple else ORANGE)
    box.set_footer(text="🦇 Halloween Bot  •  Bonbons, citrouilles et mystères")
    return box

def wait_text(seconds):
    return f"🕯️ Reviens <t:{int(time.time())+int(seconds)}:R>."

async def fail(interaction, message):
    if interaction.response.is_done():
        await interaction.followup.send(f"💀 {message}", ephemeral=True)
    else:
        await interaction.response.send_message(f"💀 {message}", ephemeral=True)

def format_rank(guild, rows, emoji="🍬"):
    if not rows:
        return "🕸️ Aucun joueur pour le moment. Utilise /daily pour commencer."
    medals=["🥇","🥈","🥉"]
    output=[]
    for n, row in enumerate(rows,1):
        member=guild.get_member(row["user_id"])
        name=discord.utils.escape_markdown(member.display_name) if member else f"Joueur {row['user_id']}"
        output.append(f"{medals[n-1] if n<4 else '🎃'} **{n}.** {name} · **{row['score']:,} {emoji}**")
    return "\n".join(output)

class OwnerView(discord.ui.View):
    def __init__(self, owner_id, timeout=180):
        super().__init__(timeout=timeout)
        self.owner_id=owner_id

    async def interaction_check(self, interaction):
        if interaction.user.id!=self.owner_id:
            await fail(interaction,"Ce menu appartient à un autre joueur.")
            return False
        return True

def authorized(interaction):
    return isinstance(interaction.user,discord.Member) and interaction.user.guild_permissions.manage_guild
