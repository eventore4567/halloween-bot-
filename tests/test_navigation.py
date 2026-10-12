import asyncio
import unittest

from helpers import FakeInteraction, make_bot

from halloween.ui import NavButton, Panel, nav, register_navigation


class NavigationTest(unittest.TestCase):
    def test_nav_pattern_survives_view_removal(self):
        bot = make_bot()
        register_navigation(bot)
        store = bot._connection._view_store
        pattern = NavButton.__discord_ui_compiled_template__

        async def go():
            import discord
            view = discord.ui.LayoutView(timeout=None)
            view.add_item(Panel().row(nav("quiz", 1, "Quiz", "crystal"), discord.ui.Button(label="x")).container())
            store.add_view(view, 1234)
            # re-render without the nav button, then drop the view entirely
            view.clear_items()
            view.add_item(Panel().row(discord.ui.Button(label="y")).container())
            store.add_view(view, 1234)
            store.remove_view(view)
        asyncio.run(go())
        self.assertIn(pattern, store._dynamic_items)

    def test_nav_button_routes_to_opener(self):
        bot = make_bot()
        calls = []

        async def opener(interaction, edit=False):
            calls.append(edit)
        bot.openers["quiz"] = opener

        async def go():
            btn = nav("quiz", 111, "Quiz", "crystal")
            inter = FakeInteraction(client=bot)
            await btn.callback(inter)
            other = FakeInteraction(client=bot)
            other.user.id = 222
            await btn.callback(other)
        asyncio.run(go())
        self.assertEqual(calls, [True, False])


if __name__ == "__main__":
    unittest.main()
