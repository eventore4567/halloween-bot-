"""UI regression tests for Halloween embeds and Discord components."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import discord

from halloween_bot.common import ICONS, FALLBACK, card, format_rank, themed_view
from halloween_bot.economy import HubView, ShopView, profile_card, shop_card, guide_card
from halloween_bot.farming import farm_card, FarmView
from halloween_bot.games import BossView, DuelView
from halloween_bot.events import EventClaim
from halloween_bot.storage import Store


class ThemeTests(unittest.TestCase):
    def setUp(self):
        ICONS.install([])
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.folder.name)/"ui.sqlite3"))
        self.bot = SimpleNamespace(store=self.store, active_bosses={})

    @staticmethod
    def make_view(factory, *args):
        async def build():
            return factory(*args)
        return asyncio.run(build())

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()
        ICONS.install([])

    def test_theme_card_has_author_footer_and_sections(self):
        panel = card("Classement test", "Une soirée Halloween.",
                     theme="gold",
                     sections=[
                         ("🍬  RÉCOMPENSE", "**+150**", True),
                         ("🎃  NOTES", "Joue encore !", False),
                     ])
        payload = panel.to_dict()
        self.assertIn("Halloween", payload["author"]["name"].title())
        self.assertIn("🎃", payload["fields"][1]["name"])
        self.assertEqual(len(payload["fields"]), 2)
        self.assertGreater(panel.color.value, 0)

    def test_application_emoji_mapping_and_fallback(self):
        class FakeEmoji:
            def __init__(self, name):
                self.name = name
            def __str__(self):
                return "<:pumpkin:123456789012345678>"
        ICONS.install([FakeEmoji("pumpkin")])
        self.assertIn("<:pumpkin:123456789012345678>", ICONS.replace("🎃 Citrouille"))
        self.assertEqual(ICONS.icon("ghost"), FALLBACK["ghost"])
        panel = card("Citrouille", "🎃 Décoration")
        self.assertIn("<:pumpkin:123456789012345678>", panel.description)

    def test_shop_is_clearly_sectioned_no_duplicate_labels(self):
        panel = shop_card()
        self.assertGreaterEqual(len(panel.fields), 3)
        view = self.make_view(ShopView, 123)
        self.assertEqual(len(view.children), 1)
        options = view.children[0].options
        self.assertEqual(len(options), 8)
        self.assertTrue(all(opt.emoji for opt in options))
        self.assertTrue(all(not opt.label.startswith(("🎃", "🦇", "👑")) for opt in options))

    def test_main_hub_buttons_and_guide(self):
        view = self.make_view(HubView, 123)
        self.assertEqual(len(view.children), 5)
        self.assertTrue(all(isinstance(button, discord.ui.Button) for button in view.children))
        self.assertGreaterEqual(len(guide_card().fields), 4)

    def test_farm_visual_sections_and_buttons(self):
        panel = farm_card(self.bot, 99, 10)
        self.assertGreaterEqual(len(panel.fields), 5)
        self.assertTrue(any("NIVEAU" in section.name for section in panel.fields))
        self.assertEqual(len(self.make_view(FarmView, 10).children), 5)

    def test_boss_visual_has_progress_and_buttons(self):
        view = self.make_view(BossView, self.bot, 99)
        panel = view.panel()
        self.assertGreaterEqual(len(panel.fields), 3)
        self.assertIn("450", panel.fields[0].value)
        self.assertEqual(len(view.children), 1)
        self.assertEqual(len(self.make_view(DuelView, 1, 2, 99).children), 2)

    def test_event_button_stays_persistent(self):
        view = self.make_view(EventClaim, self.bot, 123)
        self.assertIsNone(view.timeout)
        self.assertEqual(view.children[0].custom_id, "halloween:event:123")


if __name__ == "__main__":
    unittest.main()
