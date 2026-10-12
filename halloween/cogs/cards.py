"""/cartes — collectible monster cards with an animated reveal."""
from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from .. import config
from ..art import cards as art
from ..content.games import CARD, CARDS, COLLECTION_BONUS, RARITIES, draw_card
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, notice

PRICE = config.SHOP["booster"]["price"]


def collection_bonus(store, g, u) -> int:
    """COLLECTION_BONUS the first time a player owns all the cards (whether from boosters or trades), else 0."""
    if len(store.cards(g, u)) >= len(CARDS) and store.unlock(g, u, "collection_complete"):
        return COLLECTION_BONUS
    return 0


class CardsView(GameView):
    banner_key = "cards"
    kicker = "CARTES MAUDITES"
    owner_hint = "Ouvre ta propre collection avec /cartes."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=600)
        self.state = "collection"
        self.pulled = None
        self.duplicate = 0
        self.completed = False
        self.inspect = None

    def build(self) -> Panel:
        g, u = self.guild_id, self.owner_id
        owned = self.store.cards(g, u)
        p = Panel("purple")
        if self.state == "reveal":
            p.image("carte.gif")
            card = CARD[self.pulled]
            rar = RARITIES[card["rarity"]]
            if self.duplicate:
                body = (f"Tu l'avais déjà (×{owned.get(card['key'], 1)}). Elle se transforme en "
                        f"**+{config.fmt(self.duplicate)}** {E.candy}.")
            else:
                body = f"{E.sparkle} **NOUVELLE CARTE !** Elle rejoint ta collection."
            if self.completed:
                body += f"\n{E.crown} **COLLECTION COMPLÈTE !** Bonus de **{config.fmt(COLLECTION_BONUS)}** {E.candy} !"
            p.title(f"{card['name']} · {rar['name']}", icon=card["emoji"], body=body)
        elif self.state == "inspect":
            p.image("carte.png")
            card = CARD[self.inspect]
            p.title(card["name"], icon=card["emoji"],
                    body=f"{'★' * RARITIES[card['rarity']]['stars']} {RARITIES[card['rarity']]['name']} · "
                         f"tu en as **{owned.get(card['key'], 0)}**")
        else:
            p.banner(self.banner_key)
            p.title("Ta collection de monstres", icon="gift",
                    body=f"{E.bar(len(owned), len(CARDS), 8)} **{len(owned)}/{len(CARDS)}** cartes\n"
                         f"-# Complète la collection pour gagner **{config.fmt(COLLECTION_BONUS)}** {E.candy}. "
                         f"Les doublons sont échangés contre des bonbons.")
        p.sep()
        by_rarity = []
        for rk, rar in RARITIES.items():
            cells = []
            for card in (c for c in CARDS if c["rarity"] == rk):
                n = owned.get(card["key"], 0)
                cells.append(f"{E(card['emoji'])}" + (f"×{n}" if n > 1 else "") if n else E.lock)
            have = sum(1 for c in CARDS if c["rarity"] == rk and c["key"] in owned)
            total = sum(1 for c in CARDS if c["rarity"] == rk)
            by_rarity.append(f"**{rar['name']}** · {have}/{total} · {rar['weight']} %\n{' '.join(cells)}")
        p.text("\n".join(by_rarity))
        p.sep()
        boosters = self.store.item_qty(g, u, "booster")
        bal = self.store.candies(g, u)
        label = f"Ouvrir un booster ({boosters})" if boosters else f"Acheter un booster · {PRICE}"
        p.row(button(label, "gift", "success", self._open, disabled=not boosters and bal < PRICE),
              button("Collection", "book", "secondary", self._back, disabled=self.state == "collection"),
              nav("shop", self.owner_id, "Boutique", "witch"))
        if owned:
            opts = [discord.SelectOption(label=CARD[k]["name"], value=k, emoji=E.partial(CARD[k]["emoji"]),
                                         description=f"{RARITIES[CARD[k]['rarity']]['name']} · ×{n}")
                    for k, n in sorted(owned.items(), key=lambda kv: [c["key"] for c in CARDS].index(kv[0]))][:25]
            sel = discord.ui.Select(placeholder="Admirer une de tes cartes…", options=opts)
            sel.callback = self._inspect
            p.row(sel)
        p.footer(self.footer())
        return p

    async def _open(self, interaction):
        async with self.lock:
            g, u = self.guild_id, self.owner_id
            if not self.store.use_item(g, u, "booster"):
                try:
                    self.store.spend(g, u, PRICE, "booster")
                except NotEnough:
                    return await notice(interaction, f"Il te faut **{PRICE}** bonbons pour un booster.")
            await interaction.response.defer()
            card = draw_card()
            count = self.store.add_card(g, u, card["key"])
            self.pulled = card["key"]
            self.duplicate = 0
            self.completed = False
            if count > 1:
                self.reward = grant(self.store, g, u, RARITIES[card["rarity"]]["refund"], 5, "doublon",
                                    stats={"boosters": 1})
                self.duplicate = self.reward.candies
            else:
                bonus = collection_bonus(self.store, g, u)
                self.completed = bool(bonus)
                self.reward = grant(self.store, g, u, bonus, 15 * RARITIES[card["rarity"]]["stars"] + (200 if bonus else 0),
                                    "carte", stats={"boosters": 1})
            data = await asyncio.to_thread(art.card_reveal_gif, card["key"])
            self.state = "reveal"
            await self.refresh(interaction, attachments=[image_file(data, "carte.gif")])

    async def _inspect(self, interaction):
        key = interaction.data["values"][0]
        await interaction.response.defer()
        data = await asyncio.to_thread(art.card_png, key)
        self.inspect = key
        self.state = "inspect"
        await self.refresh(interaction, attachments=[image_file(data, "carte.png")])

    async def _back(self, interaction):
        from ..ui import banner_file
        await interaction.response.defer()
        self.state = "collection"
        await self.refresh(interaction, attachments=[await banner_file(self.banner_key)])


class Cards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["cards"] = self.open

    async def open(self, interaction, edit=False):
        await CardsView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="cartes", description="🎁 Cartes maudites : ouvre des boosters et collectionne les 24 monstres")
    @app_commands.guild_only()
    async def cartes(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Cards(bot))
