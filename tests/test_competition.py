"""Critical competition invariants for a real-prize organizer.

Tournament awards are independent of candies and random games. Every attempt is
owner-bound, single-use, time-limited and unique per challenge/day/season.
"""
from __future__ import annotations

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path

from halloween_bot.competition_store import (
    Competition, MODES, calendar_day, division, generate_puzzle,
    normalize
)
from halloween_bot.storage import Store


class CompetitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "halloween.sqlite3"))
        self.comp = Competition(self.store)
        self.now = 1_790_000_000
        self.ends = self.now + 14 * 86400

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def launch(self, guild=1, **kwargs):
        return self.comp.start(
            guild, 99, self.ends, now=self.now, **kwargs
        )

    def join(self, guild=1, member=10):
        self.assertEqual(self.comp.join(guild, member, now=self.now + 1),
                         "welcome")

    def test_contest_requires_organizer_start(self):
        self.assertIsNone(self.comp.season(1, now=self.now))
        self.assertEqual(self.comp.join(1, 10, now=self.now), "closed")
        self.assertEqual(self.comp.issue(
            1, 10, "calcul", "1+1", "2", now=self.now
        )["status"], "closed")

    def test_start_and_free_entry(self):
        self.assertEqual(self.launch()["status"], "started")
        self.join()
        self.assertEqual(self.comp.join(1, 10, now=self.now + 2), "joined")
        self.assertEqual(self.comp.position(1, 10, now=self.now + 2)["score"], 0)

    def test_real_prize_requires_rules_url(self):
        self.assertEqual(self.launch(prize_label="1 000 €")["status"],
                         "rules_required")
        self.assertEqual(self.launch(prize_label="1 000 €",
                                     rules_url="http://example.com/rules")["status"],
                         "rules_required")
        self.assertEqual(self.launch(prize_label="1 000 €",
                                     rules_url="https://example.com/reglement")["status"],
                         "started")

    def test_cannot_create_simultaneous_seasons(self):
        self.launch()
        self.assertEqual(self.launch()["status"], "already_running")

    def test_bad_end_dates_rejected(self):
        for end in [self.now, self.now + 10, self.now + 90 * 86400]:
            self.assertEqual(self.comp.start(1, 99, end, now=self.now)["status"],
                             "bad_date")

    def test_no_paid_currency_can_score_tournament(self):
        self.launch()
        self.join()
        self.store.award(1, 10, 999_000, ghosts=25, quizzes=100,
                         duel_wins=42, harvests=99)
        self.store.gift(1, 10, 11, 500)
        self.assertEqual(self.comp.position(1, 10, now=self.now + 2)["score"], 0)
        self.assertIsNone(self.comp.position(1, 11, now=self.now + 2))

    def test_correct_answer_awards_exact_points(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "calcul",
                                 "Combien font deux plus deux ?", "4",
                                 now=self.now + 2)
        self.assertEqual(issued["status"], "issued")
        result = self.comp.answer(issued["attempt_id"], 1, 10, " 4 ",
                                  now=self.now + 4)
        self.assertEqual(result, {"status": "correct", "points": 100,
                                  "mode": "calcul"})
        self.assertEqual(self.comp.position(1, 10, now=self.now + 6)["score"], 100)
        self.assertEqual(self.comp.position(1, 10, now=self.now + 6)["solved"], 1)
        self.assertEqual(self.store.profile(1, 10)["candies"], 0)
        rows, season = self.comp.audit(1, now=self.now + 6)
        self.assertEqual(rows[0]["outcome"], "correct")
        self.assertEqual(rows[0]["points"], 100)

    def test_wrong_answer_only_consumes_attempt(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "mot", "Mot ?", "citrouille",
                                 now=self.now + 2)
        result = self.comp.answer(issued["attempt_id"], 1, 10, "Fantome",
                                  now=self.now + 3)
        self.assertEqual(result["status"], "incorrect")
        self.assertEqual(self.comp.position(1, 10, now=self.now + 5)["score"], 0)
        self.assertEqual(self.comp.issue(
            1, 10, "mot", "Mot ?", "citrouille", now=self.now + 6
        )["status"], "already_today")

    def test_owner_and_guild_bound(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "code", "Code ?", "17",
                                 now=self.now + 2)
        attempt_id = issued["attempt_id"]
        self.assertEqual(self.comp.answer(attempt_id, 1, 11, "17",
                                          now=self.now + 3)["status"], "forbidden")
        self.assertEqual(self.comp.answer(attempt_id, 2, 10, "17",
                                          now=self.now + 3)["status"], "forbidden")
        self.assertEqual(self.comp.answer(attempt_id, 1, 10, "17",
                                          now=self.now + 4)["status"], "correct")

    def test_double_submit_concurrent_only_once(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "code", "Code ?", "17",
                                 now=self.now + 2)
        results = []

        def complete():
            results.append(self.comp.answer(
                issued["attempt_id"], 1, 10, "17", now=self.now + 3
            )["status"])

        threads = [threading.Thread(target=complete) for _ in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(results.count("correct"), 1)
        self.assertEqual(results.count("used"), 19)
        self.assertEqual(self.comp.position(1, 10, now=self.now + 5)["score"], 160)

    def test_one_attempt_each_mode_per_utc_day(self):
        self.launch()
        self.join()
        for mode in MODES:
            self.assertEqual(self.comp.issue(
                1, 10, mode, "Question ?", "answer", now=self.now + 2
            )["status"], "issued")
        self.assertEqual(self.comp.remaining_modes(1, 10, now=self.now + 10), [])
        tomorrow = (self.now // 86400 + 1) * 86400 + 10
        self.assertEqual(len(self.comp.remaining_modes(1, 10, now=tomorrow)), 3)

    def test_expired_attempt_no_points(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "calcul", "1+1", "2",
                                 now=self.now + 2)
        self.assertEqual(self.comp.answer(
            issued["attempt_id"], 1, 10, "2",
            now=issued["expires_at"] + 1
        )["status"], "expired")
        self.assertEqual(self.comp.position(1, 10, now=self.now + 200)["score"], 0)

    def test_closing_season_freezes_score(self):
        self.launch()
        self.join()
        issued = self.comp.issue(1, 10, "code", "Question ?", "42",
                                 now=self.now + 3)
        self.assertTrue(self.comp.close(1, now=self.now + 4))
        self.assertEqual(self.comp.answer(issued["attempt_id"], 1, 10, "42",
                                          now=self.now + 5)["status"], "expired")
        self.assertEqual(self.comp.join(1, 11, now=self.now + 5), "closed")
        self.assertEqual(self.comp.position(1, 10, now=self.now + 5)["score"], 0)

    def test_season_expires_automatically(self):
        self.launch()
        self.join()
        self.assertEqual(self.comp.season(1, now=self.ends)["status"], "closed")
        self.assertEqual(self.comp.join(1, 11, now=self.ends), "closed")

    def test_multi_server_isolation(self):
        self.launch(1)
        self.launch(2)
        self.join(1, 10)
        self.join(2, 10)
        issued = self.comp.issue(1, 10, "calcul", "1+1", "2",
                                 now=self.now + 2)
        self.comp.answer(issued["attempt_id"], 1, 10, "2", now=self.now + 3)
        self.assertEqual(self.comp.position(1, 10, now=self.now + 4)["score"], 100)
        self.assertEqual(self.comp.position(2, 10, now=self.now + 4)["score"], 0)

    def test_score_ties_are_explicit_and_same_rank(self):
        self.launch()
        self.join(1, 10)
        self.join(1, 20)
        self.join(1, 30)
        for person in [10, 20]:
            issued = self.comp.issue(
                1, person, "calcul", "1+1", "2", now=self.now + 3
            )
            self.comp.answer(issued["attempt_id"], 1, person, "2",
                             now=self.now + 4)
        self.assertEqual([r["place"] for r in self.comp.standings(
            1, now=self.now + 6
        )], [1, 1, 3])
        self.assertEqual(self.comp.position(1, 20, now=self.now + 6)["place"], 1)

    def test_divisions_cover_uneven_score_steps(self):
        expected = [
            (0, "Bronze"), (350, "Argent"), (950, "Or"),
            (2200, "Diamant"), (4500, "Légende"),
        ]
        for value, name in expected:
            self.assertIn(name, division(value)[0])

    def test_nonnumeric_puzzle_and_normalization(self):
        self.assertEqual(normalize("CITROUÏLLE  "), "citrouille")
        for mode in MODES:
            prompt, answer = generate_puzzle(mode)
            self.assertTrue(len(prompt) >= 20)
            self.assertTrue(answer)
            self.assertTrue(normalize(answer))

    def test_restart_preserves_tournament(self):
        self.launch()
        self.join()
        issue = self.comp.issue(1, 10, "calcul", "1 + 1", "2",
                                now=self.now + 3)
        self.store.close()
        self.store = Store(str(Path(self.temp.name) / "halloween.sqlite3"))
        self.comp = Competition(self.store)
        self.assertEqual(self.comp.answer(
            issue["attempt_id"], 1, 10, "2", now=self.now + 4
        )["status"], "correct")
        self.assertEqual(self.comp.position(1, 10, now=self.now + 6)["score"], 100)


if __name__ == "__main__":
    unittest.main()
