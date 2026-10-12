"""Every panel renders in all its states and respects Discord's limits."""
import asyncio
import unittest

from helpers import FakeInteraction, FakeUser, check_layout, install_fake_emojis, make_bot

from halloween.cogs import cards, daily, expedition, formula, hangman, hub, hunt, leaderboard, memory, quiz, shop, wheel
from halloween.cogs.drops import BossView, FlashQuizView, LootView
from halloween.cogs.duel import DuelView
from halloween.cogs.profile import ProfileView


def run(coro):
    return asyncio.run(coro)


class ViewsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_emojis()  # custom emojis make the text much longer: test the worst case
        cls.bot = make_bot()
        cls.store = cls.bot.store
        cls.store.add_candies(999, 111, 5000, "test", boost=False)

    def render(self, view):
        view.render()
        return check_layout(view)

    def test_hub_both_pages(self):
        async def go():
            v = hub.HubView(self.bot, FakeInteraction())
            self.render(v)
            v.page = "guide"
            self.render(v)
        run(go())

    def test_profile(self):
        async def go():
            i = FakeInteraction()
            self.store.give_item(999, 111, "joker", 2)
            self.store.add_effect(999, 111, "luck", 60)
            self.render(ProfileView(self.bot, i, i.user))
        run(go())

    def test_show_every_state(self):
        async def go():
            v = quiz.ShowView(self.bot, FakeInteraction())
            self.render(v)
            for rung in range(12):
                v.correct_count = rung
                v._prepare()
                v.state, v.image, v.deadline = "question", quiz.GIF_NAME, 0
                self.render(v)
                v.hint = "x" * 200
                self.render(v)
                v.state, v.result = "answer", "Bonne réponse !\nbravo"
                self.render(v)
            from halloween.rewards import Reward
            for how in ("top", "cash", "fall"):
                v.state, v.final, v.result = "end", dict(how=how, amount=10, reward=Reward(candies=10)), "fin"
                self.render(v)
            v.state = "empty"
            self.render(v)
        run(go())

    def test_expedition_states(self):
        async def go():
            self.store.add_card(999, 111, "c_bat")
            v = expedition.ExpeditionView(self.bot, FakeInteraction())
            self.render(v)
            v.team = ["c_bat"]
            v.report = "### ok"
            self.render(v)
            for dest in expedition.DEST:
                v.dest = dest
                self.render(v)
            self.store.meta_set("exp:999:111", dict(dest="castle", team=["c_bat"], chance=0.5, mult=1.1, ends=0))
            self.render(v)
            self.store.meta_del("exp:999:111")
        run(go())

    def test_formula_states(self):
        async def go():
            v = formula.FormulaView(self.bot, FakeInteraction(), True)
            self.render(v)
            for _ in range(7):
                v.history.append((list(v.secret[::-1]), 0, 4))
            v.current = v.secret[:2]
            self.render(v)
            from halloween.rewards import Reward
            v.state, v.potion, v.effect, v.reward = "won", "fortune", "effet", Reward(candies=5)
            self.render(v)
            v.state = "lost"
            self.render(v)
            self.render(formula.FormulaView(self.bot, FakeInteraction(), False))
        run(go())

    def test_wheel_states(self):
        async def go():
            v = wheel.WheelView(self.bot, FakeInteraction())
            self.render(v)
            v.state, v.target, v.result_text = "done", 7, "jackpot"
            self.render(v)
        run(go())

    def test_memory_and_hunt_and_hangman(self):
        async def go():
            for cls in (memory.MemoryView, hunt.HuntView, hangman.HangmanView):
                v = cls(self.bot, FakeInteraction(), True)
                self.render(v)
                v.on_expire()
                self.render(v)
                self.render(cls(self.bot, FakeInteraction(), False))
        run(go())

    def test_cards_and_shop_and_daily(self):
        async def go():
            self.store.add_card(999, 111, "l_reaper")
            v = cards.CardsView(self.bot, FakeInteraction())
            self.render(v)
            v.state, v.pulled, v.duplicate = "reveal", "l_reaper", 500
            self.render(v)
            v.state, v.inspect = "inspect", "l_reaper"
            self.render(v)
            self.render(shop.ShopView(self.bot, FakeInteraction()))
            d = daily.DailyView(self.bot, FakeInteraction())
            for state in ("claimed", "opening"):
                d.state = state
                self.render(d)
        run(go())

    def test_leaderboard(self):
        async def go():
            for kind in leaderboard.BOARDS:
                self.render(leaderboard.TopView(self.bot, FakeInteraction(), kind))
        run(go())

    def test_events(self):
        async def go():
            cog = self.bot.get_cog("Drops")
            for v in (LootView(cog, 999), FlashQuizView(cog, 999), BossView(cog, 999, 3)):
                self.render(v)
                v.over = True
                self.render(v)
        run(go())

    def test_duel(self):
        async def go():
            v = DuelView(self.bot, FakeInteraction(), FakeUser(222, "Jimmy"), 100)
            check_layout(v)
            v.state = "play"
            v.render()
            check_layout(v)
            v.choice = {111: "vampire", 222: "werewolf"}
            self.store.add_candies(999, 222, 500, "test", boost=False)
            v._resolve_round()
            self.assertEqual(v.score[111], 1)
            v.render()
            check_layout(v)
        run(go())


if __name__ == "__main__":
    unittest.main()
