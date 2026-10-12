"""/familier — adopt a haunted pet: feed it, play with it, it brings candies back and evolves."""
from __future__ import annotations

import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from ..art.pet import pet_gif
from ..content import pet as P
from ..db import NotEnough
from ..emojis import E
from ..rewards import grant
from ..ui import GameView, Panel, button, image_file, nav, relative

GIF_NAME = "familier.gif"
DEFAULT_NAMES = {"ghost": "Bouh", "bat": "Nocturne", "pumpkin": "Potiron", "spider": "Tisseuse", "werewolf": "Croc"}


def pet_key(g, u):
    return f"pet:{g}:{u}"


class RenameModal(discord.ui.Modal, title="Renommer ton familier"):
    name = discord.ui.TextInput(label="Nouveau nom", min_length=1, max_length=24)

    def __init__(self, view: "PetView"):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction):
        await self.view.rename(interaction, str(self.name.value))


class PetView(GameView):
    banner_key = None
    kicker = "FAMILIER HANTÉ"
    owner_hint = "Adopte ton propre familier avec /familier."

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction, timeout=600)
        self.key = pet_key(self.guild_id, self.owner_id)
        self.pet = self.store.meta_get(self.key)
        if self.pet:
            P.decay(self.pet)
        self.flash = ""
        if not self.pet:
            self.banner_key = "pet"

    # --------------------------------------------------------------- helpers
    def save(self):
        self.store.meta_set(self.key, self.pet)

    def picture(self) -> bytes:
        p = self.pet
        sp = P.SPECIES[p["species"]]
        idx, name = P.stage(p["level"])
        need = P.xp_for(p["level"])
        return pet_gif(sp["icon"], sp["color"], idx, p["name"], name, p["level"], p["hunger"], p["joy"],
                       0 if p["level"] >= P.MAX_LEVEL else p["xp"] / need, seed=p["level"])

    async def extra_files(self):
        if not self.pet:
            return []
        return [image_file(await asyncio.to_thread(self.picture), GIF_NAME)]

    def _cd(self, key):
        return self.store.cooldown_left(self.guild_id, self.owner_id, key)

    # ---------------------------------------------------------------- render
    def build(self) -> Panel:
        p = Panel("purple")
        if not self.pet:
            p.banner("pet")
            p.title("Adopte un familier hanté", icon="heart",
                    body="Il grandit avec toi, te rapporte des bonbons toutes les 4 heures et **évolue** : "
                         "bébé, jeune, adulte… puis **légendaire** et couronné !\n"
                         "Nourris-le et joue avec lui : plus il est heureux, plus son butin est gros.")
            options = [discord.SelectOption(label=s["name"], value=k, emoji=E.partial(s["icon"]),
                                            description=f"Il raffole {s['food']}"[:100])
                       for k, s in P.SPECIES.items()]
            select = discord.ui.Select(placeholder="Choisis ton compagnon…", options=options)
            select.callback = self._adopt
            p.row(select)
            p.footer(self.footer())
            return p
        pet = self.pet
        sp = P.SPECIES[pet["species"]]
        idx, stage_name = P.stage(pet["level"])
        p.image(GIF_NAME)
        body = (f"{E(sp['icon'])} **{pet['name']}** ({sp['name']} · {stage_name} niv. **{pet['level']}**) "
                f"{P.mood_text(pet)}")
        if self.flash:
            body = self.flash + "\n" + body
        p.title(pet["name"], icon=sp["icon"], body=body)
        loot = self._cd("pet_loot")
        play = self._cd("pet_play")
        caress = self._cd("pet_pet")
        nxt = [s for s in P.STAGES if s[0] > pet["level"]]
        p.text(f"-# {E.candy_bag} Butin : " + (f"de retour {relative(time.time() + loot)}" if loot else "**prêt !**")
               + (f" · prochaine évolution au niveau **{nxt[0][0]}** ({nxt[0][1]})" if nxt else " · forme ultime atteinte"))
        p.row(button(f"Nourrir ({P.FEED_COST})", "candy", "success", self._feed,
                     disabled=pet["hunger"] >= 95),
              button("Jouer", "ghost", "primary", self._play, disabled=bool(play)),
              button("Caresser", "heart", "secondary", self._caress, disabled=bool(caress)),
              button("Butin", "candy_bag", "success", self._loot, disabled=bool(loot)))
        p.row(button("Renommer", "scroll", "secondary", self._rename), nav("hub", self.owner_id, "Tous les jeux", "pumpkin"))
        p.footer(self.footer())
        return p

    async def _redraw(self, interaction):
        self.save()
        await interaction.response.defer()
        data = await asyncio.to_thread(self.picture)
        await self.refresh(interaction, attachments=[image_file(data, GIF_NAME)])

    def _gain(self, xp: int) -> str:
        before = P.stage(self.pet["level"])[0]
        levels = P.add_xp(self.pet, xp)
        if not levels:
            return ""
        lvl = self.pet["level"]
        r = grant(self.store, self.guild_id, self.owner_id, 0, 0, "familier", best={"pet_level": lvl})
        text = f"\n{E.sparkle} **{self.pet['name']} passe au niveau {lvl} !**"
        idx, name = P.stage(lvl)
        if idx > before:
            text += f" {E.crown} **Il évolue : {name} !**"
        if r.achievements:
            text += "\n" + r.line()
        return text

    # --------------------------------------------------------------- actions
    async def _adopt(self, interaction):
        async with self.lock:
            if self.pet:
                return await interaction.response.defer()
            species = interaction.data["values"][0]
            self.pet = P.new_pet(species, DEFAULT_NAMES[species])
            self.flash = f"{E.heart} Bienvenue à **{self.pet['name']}** ! Tu peux le renommer quand tu veux."
            await self._redraw(interaction)

    async def _feed(self, interaction):
        async with self.lock:
            g, u = self.guild_id, self.owner_id
            P.decay(self.pet)
            try:
                self.store.spend(g, u, P.FEED_COST, "familier-repas")
            except NotEnough:
                self.flash = f"{E.cross} Il te faut **{P.FEED_COST}** bonbons pour le nourrir."
                return await self.refresh(interaction)
            food = P.SPECIES[self.pet["species"]]["food"]
            self.pet["hunger"] = min(100.0, self.pet["hunger"] + P.FEED_HUNGER)
            self.flash = f"{E.candy} Tu lui donnes {food}. Miam !" + self._gain(10)
            await self._redraw(interaction)

    async def _play(self, interaction):
        async with self.lock:
            if not self.store.take_cooldown(self.guild_id, self.owner_id, "pet_play", P.PLAY_COOLDOWN):
                return await interaction.response.defer()
            P.decay(self.pet)
            self.pet["joy"] = min(100.0, self.pet["joy"] + P.PLAY_JOY)
            found = random.randint(10, 25 + 2 * self.pet["level"])
            r = grant(self.store, self.guild_id, self.owner_id, found, 5, "familier")
            game = random.choice(["à cache-cache dans le cimetière", "à attraper des chauves-souris",
                                  "à effrayer les passants", "à la balle (une citrouille)"])
            self.flash = f"{E.ghost} Vous jouez {game} ! Il trouve des bonbons : {r.line()}" + self._gain(15)
            await self._redraw(interaction)

    async def _caress(self, interaction):
        async with self.lock:
            if not self.store.take_cooldown(self.guild_id, self.owner_id, "pet_pet", P.PET_COOLDOWN):
                return await interaction.response.defer()
            P.decay(self.pet)
            self.pet["joy"] = min(100.0, self.pet["joy"] + P.PET_JOY)
            self.flash = f"{E.heart} {self.pet['name']} frissonne de plaisir." + self._gain(5)
            await self._redraw(interaction)

    async def _loot(self, interaction):
        async with self.lock:
            if not self.store.take_cooldown(self.guild_id, self.owner_id, "pet_loot", P.LOOT_COOLDOWN):
                return await interaction.response.defer()
            P.decay(self.pet)
            amount = P.loot_amount(self.pet)
            r = grant(self.store, self.guild_id, self.owner_id, amount, 10, "familier")
            self.flash = f"{E.candy_bag} {self.pet['name']} revient de sa virée nocturne : {r.line()}" + self._gain(20)
            await self._redraw(interaction)

    async def _rename(self, interaction):
        await interaction.response.send_modal(RenameModal(self))

    async def rename(self, interaction, name: str):
        async with self.lock:
            name = " ".join(name.split())[:24] or self.pet["name"]
            self.pet["name"] = name
            self.flash = f"{E.scroll} Ton familier s'appelle désormais **{name}**."
            await self._redraw(interaction)


class Pet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.openers["pet"] = self.open

    async def open(self, interaction, edit=False):
        await PetView(self.bot, interaction).start(interaction, edit)

    @app_commands.command(name="familier", description="🦇 Ton familier hanté : nourris-le, joue, fais-le évoluer")
    @app_commands.guild_only()
    async def familier(self, interaction: discord.Interaction):
        await self.open(interaction)


async def setup(bot):
    await bot.add_cog(Pet(bot))
