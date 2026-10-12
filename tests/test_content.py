import random
import unittest
from collections import Counter

from halloween import config
from halloween.cogs.daily import daily_amount
from halloween.cogs.duel import MOVES, judge
from halloween.cogs.hangman import hangman_reward, reveal, solved
from halloween.cogs.hunt import REAPERS, make_board
from halloween.cogs.memory import memory_reward
from halloween.cogs.formula import formula_reward, score
from halloween.cogs.quiz import audience_poll, ghost_hint
from halloween.content import quiz_bank
from halloween.content.games import CARDS, HANGMAN, RARITIES, SHADOWS, draw_card


class QuizBankTest(unittest.TestCase):
    def test_bank_is_big_and_balanced(self):
        self.assertGreaterEqual(quiz_bank.TOTAL, 680)
        self.assertEqual(sorted(quiz_bank.BY_LEVEL), [1, 2, 3, 4, 5])
        for level, qs in quiz_bank.BY_LEVEL.items():
            self.assertGreaterEqual(len(qs), 80, level)

    def test_questions_are_clean(self):
        for q in quiz_bank.QUESTIONS:
            self.assertEqual(len(q.wrong), 3)
            self.assertNotIn(q.answer, q.wrong)
            self.assertLessEqual(len(q.text), 200, q.text)
            for a in (q.answer, *q.wrong):
                self.assertLessEqual(len(a), 70, a)

    def test_ids_unique(self):
        self.assertEqual(len({q.qid for q in quiz_bank.QUESTIONS}), quiz_bank.TOTAL)

    def test_pick_prefers_unseen_and_resets(self):
        pool = quiz_bank.BY_LEVEL[5]
        seen = {q.qid for q in pool[1:]}
        q, reset = quiz_bank.pick(5, seen)
        self.assertEqual((q, reset), (pool[0], False))
        _, reset = quiz_bank.pick(5, {q.qid for q in pool})
        self.assertTrue(reset)

    def test_shuffle_keeps_answer(self):
        q = quiz_bank.QUESTIONS[0]
        opts, idx = q.shuffled(random.Random(4))
        self.assertEqual(opts[idx], q.answer)
        self.assertEqual(sorted(opts), sorted([q.answer, *q.wrong]))


class GameLogicTest(unittest.TestCase):
    def test_show_ladder(self):
        self.assertEqual(len(config.SHOW_LADDER), len(config.SHOW_LEVELS))
        self.assertEqual(config.SHOW_LADDER, sorted(config.SHOW_LADDER))
        self.assertEqual(config.show_safe_amount(0), 0)
        self.assertEqual(config.show_safe_amount(4), 0)
        self.assertEqual(config.show_safe_amount(5), config.SHOW_LADDER[4])
        self.assertEqual(config.show_safe_amount(11), config.SHOW_LADDER[8])
        for lvl in config.SHOW_LEVELS:
            self.assertIn(lvl, quiz_bank.BY_LEVEL)

    def test_lifelines(self):
        rnd = random.Random(2)
        for level in range(1, 6):
            poll = audience_poll(1, {0, 3}, level, rnd)
            self.assertEqual(sorted(poll), [1, 2])
            self.assertEqual(sum(poll.values()), 100)
            self.assertIn(ghost_hint(2, {0}, level, rnd), (1, 2, 3))
        hits = sum(ghost_hint(0, set(), 1, rnd) == 0 for _ in range(500))
        self.assertGreater(hits, 430)

    def test_shadow_creatures(self):
        from halloween.art.emoji_art import EMOJIS
        self.assertGreaterEqual(len(SHADOWS), 20)
        for key, name in SHADOWS:
            self.assertIn(key, EMOJIS)
        self.assertEqual(len({n for _, n in SHADOWS}), len(SHADOWS))

    def test_formula_scoring(self):
        self.assertEqual(score(["a", "b", "c", "d"], ["a", "b", "c", "d"]), (4, 0))
        self.assertEqual(score(["a", "b", "c", "d"], ["d", "c", "b", "a"]), (0, 4))
        self.assertEqual(score(["a", "b", "c", "d"], ["a", "c", "e", "f"]), (1, 1))
        self.assertGreater(formula_reward(1), formula_reward(8))
        self.assertGreaterEqual(formula_reward(20), 50)

    def test_memory_reward_bounds(self):
        self.assertEqual(memory_reward(8), 240)
        self.assertEqual(memory_reward(100), 40)

    def test_hunt_board(self):
        board = make_board(random.Random(3))
        c = Counter(board)
        self.assertEqual((c["reaper"], c["chest"], len(board)), (REAPERS, 1, 20))

    def test_hangman_helpers(self):
        self.assertEqual(reveal("FANTÔME", {"O", "F"}), "F _ _ _ Ô _ _")
        self.assertTrue(solved("LOUP-GAROU", set("LOUPGAR")))
        self.assertFalse(solved("CHAT NOIR", set("CHATNO")))
        self.assertGreater(hangman_reward(7), hangman_reward(1))
        for word, hint in HANGMAN:
            self.assertTrue(word.isupper() and hint)

    def test_duel_cycle(self):
        for a in MOVES:
            self.assertEqual(judge(a, a), 0)
            wins = [b for b in MOVES if judge(a, b) == 1]
            self.assertEqual(len(wins), 1)
            self.assertEqual(judge(wins[0], a), -1)

    def test_daily_amount_grows_with_streak(self):
        self.assertLess(daily_amount(1, random.Random(0)), daily_amount(7, random.Random(0)))
        top = config.DAILY_BASE + config.DAILY_STREAK_STEP * (config.DAILY_STREAK_MAX - 1)
        for streak in (7, 30):
            self.assertTrue(top <= daily_amount(streak) <= top + 50)


class ContentTest(unittest.TestCase):
    def test_cards(self):
        self.assertEqual(len(CARDS), 24)
        self.assertEqual(len({c["key"] for c in CARDS}), 24)
        rnd = random.Random(1)
        draws = Counter(draw_card(rnd)["rarity"] for _ in range(4000))
        self.assertTrue(draws["C"] > draws["R"] > draws["E"] > draws["L"] > 0, draws)
        self.assertEqual(set(RARITIES), {"C", "R", "E", "L"})

    def test_wheel_segments(self):
        self.assertEqual(len(config.WHEEL), 8)
        for seg in config.WHEEL:
            self.assertIn(seg["kind"], {"candy", "item", "xp", "nothing"})

    def test_levels(self):
        self.assertEqual(config.level_from_xp(0)[0], 1)
        total = sum(config.xp_for_next(l) for l in range(1, 10))
        self.assertEqual(config.level_from_xp(total)[0], 10)
        self.assertEqual(config.rank_title(1), "Petit Fantôme")
        self.assertEqual(config.rank_title(99), "Légende d'Halloween")


if __name__ == "__main__":
    unittest.main()
