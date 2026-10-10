"""Automatic CRYPT CUP registration, round-state, skill scoring and V2 UI tests."""
from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from halloween_bot.storage import Store
from halloween_bot.round_store import RoundStore, PLAY_MINUTES
from halloween_bot.competition_store import Competition
from halloween_bot.quiz_content import DIFFICULTIES,QUESTIONS,FILMS,generate_film,generate_question


class RoundStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/"test.sqlite3")
        self.db=Store(self.path)
        self.competition=Competition(self.db)
        self.rounds=RoundStore(self.db)
        self.now=1790000000
        self.competition.start(7,99,self.now+8*86400,now=self.now)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def configure(self, interval=60, signup=10):
        self.rounds.configure(7,channel_id=100,role_id=200,
                              interval_min=interval,signup_min=signup)

    def begin(self):
        self.configure()
        self.assertEqual(self.rounds.enable(7,now=self.now),"enabled")
        ids=self.rounds.claim_due(now=self.now)
        self.assertEqual(len(ids),1)
        return ids[0]

    def test_no_pings_before_setup(self):
        self.assertEqual(self.rounds.enable(7,now=self.now),"incomplete")
        self.assertEqual(self.rounds.claim_due(now=self.now),[])

    def test_config_validation_and_allowed_cadence(self):
        self.configure(interval=30,signup=30)
        data=self.rounds.config(7)
        self.assertEqual((data["interval_min"],data["signup_min"]),(30,30))
        with self.assertRaises(ValueError):
            self.rounds.configure(7,interval_min=5)
        with self.assertRaises(ValueError):
            self.rounds.configure(7,signup_min=75)
        with self.assertRaises(ValueError):
            self.rounds.configure(7,role_id=-1)

    def test_one_signup_message_one_signup(self):
        round_id=self.begin()
        self.assertEqual(self.rounds.claim_due(now=self.now),[])
        self.assertEqual(self.rounds.join(round_id,7,10,now=self.now+3),"joined")
        self.assertEqual(self.rounds.join(round_id,7,10,now=self.now+4),"already_joined")
        self.assertEqual(self.rounds.count(round_id),1)
        self.assertEqual(self.rounds.join(round_id,8,20,now=self.now+4),"closed")

    def test_no_restart_duplicate_round(self):
        round_id=self.begin()
        self.db.close()
        self.db=Store(self.path)
        self.competition=Competition(self.db)
        self.rounds=RoundStore(self.db)
        self.assertEqual(self.rounds.current(7)["id"],round_id)
        self.assertEqual(self.rounds.claim_due(now=self.now+100),[])
        self.assertEqual(self.rounds.count(round_id),0)

    def test_registration_close_match_activate_results(self):
        round_id=self.begin()
        self.rounds.join(round_id,7,10,now=self.now+5)
        deadline=self.now+600
        self.assertEqual(self.rounds.join(round_id,7,11,now=deadline),"closed")
        self.assertEqual(self.rounds.activate_due(now=deadline),[round_id])
        row=self.rounds.round(round_id)
        self.assertEqual(row["status"],"active")
        self.assertEqual(row["ends_at"],deadline+PLAY_MINUTES*60)
        self.assertEqual(self.rounds.check(7,10,now=deadline+2)[0],"ready")
        self.assertEqual(self.rounds.check(7,11,now=deadline+2)[0],"not_joined")
        self.assertEqual(self.rounds.finish_due(now=row["ends_at"]-1),[])
        self.assertEqual(self.rounds.finish_due(now=row["ends_at"]),[round_id])
        self.assertEqual(self.rounds.check(7,10,now=row["ends_at"]+1)[0],"no_round")

    def test_scoring_requires_join_and_active_window(self):
        rid=self.begin()
        self.competition.join(7,10,now=self.now+1)
        self.competition.join(7,11,now=self.now+1)
        issued=lambda user,now:self.competition.issue(
            7,user,"calcul","Question ?","42",now=now
        )
        self.assertEqual(issued(10,self.now+4)["status"],"not_active_round")
        self.rounds.join(rid,7,10,now=self.now+5)
        self.rounds.activate_due(now=self.now+600)
        self.assertEqual(issued(11,self.now+601)["status"],"round_not_joined")
        self.assertEqual(issued(10,self.now+601)["status"],"issued")
        self.assertEqual(issued(10,self.now+602)["status"],"already_round")
        scores=self.competition.position(7,10,now=self.now+604)
        self.assertEqual(scores["score"],0)

    def test_round_score_isolation(self):
        rid=self.begin()
        self.competition.join(7,10,now=self.now+2)
        self.rounds.join(rid,7,10,now=self.now+4)
        self.rounds.activate_due(now=self.now+600)
        attempt=self.competition.issue(
            7,10,"calcul","2+2","4",now=self.now+601
        )
        self.assertEqual(attempt["status"],"issued")
        result=self.competition.answer(
            attempt["attempt_id"],7,10,"4",now=self.now+603
        )
        self.assertEqual(result["points"],100)
        self.assertEqual(self.rounds.round_standings(rid)[0]["score"],100)

    def test_no_duplicate_enable_or_prize_without_rules(self):
        self.configure()
        self.rounds.configure(7,prize_label="1 000 €")
        self.assertEqual(self.rounds.enable(7,now=self.now),"rules_required")
        self.rounds.configure(7,rules_url="https://example.org/reglement")
        self.assertEqual(self.rounds.enable(7,now=self.now),"enabled")
        next_at=self.rounds.config(7)["next_at"]
        self.assertEqual(self.rounds.enable(7,now=self.now+5),"already_enabled")
        self.assertEqual(self.rounds.config(7)["next_at"],next_at)

    def test_suspending_stops_future_announcements(self):
        self.begin()
        self.rounds.suspend(7)
        self.assertFalse(self.rounds.config(7)["enabled"])
        self.assertEqual(self.rounds.claim_due(now=self.now+100000),[])


class QuizQuestionTests(unittest.TestCase):
    def test_all_categories_and_difficulties(self):
        self.assertEqual(len(QUESTIONS),4)
        self.assertEqual(len(DIFFICULTIES),4)
        for category in QUESTIONS:
            for difficulty in DIFFICULTIES:
                data=generate_question(category,difficulty)
                self.assertEqual(len(set(data["answers"])),4)
                self.assertEqual(len(data["answers"]),4)
                self.assertIn(data["correct"],range(4))
                self.assertGreaterEqual(data["time"],30)

    def test_films_have_valid_source_and_four_options(self):
        self.assertGreaterEqual(len(FILMS),5)
        for level in ("facile","moyen","difficile"):
            film=generate_film(level)
            self.assertIn("commons.wikimedia.org",film["source"])
            self.assertTrue(film["image"].startswith("https://"))
            self.assertEqual(len(set(film["answers"])),4)
            self.assertEqual(film["question"],"Quel est le titre de ce film d'horreur ?")


class ComponentsV2Tests(unittest.TestCase):
    @staticmethod
    def run_in_loop(func):
        async def main():
            return func()
        return asyncio.run(main())

    def test_arena_layouts_have_actual_containers_and_buttons(self):
        import discord
        from halloween_bot.visuals import (
            CompetitionHome,PodiumView,RoundSignupLayout,
            RoundActiveLayout,RoundEndedLayout
        )
        with tempfile.TemporaryDirectory() as d:
            s=Store(str(Path(d)/"test.sqlite3"))
            comp=Competition(s)
            rnd=RoundStore(s)
            now=int(time.time())
            comp.start(7,99,now+5*86400,now=now)
            row={
                "id":9,"guild_id":7,"signup_ends_at":now+600,
                "ends_at":now+1200,"status":"signup"
            }
            guild=SimpleNamespace(id=7,get_member=lambda i:None)
            user=SimpleNamespace(id=10)
            bot=SimpleNamespace(competition=comp,round_store=rnd,store=s)
            views=self.run_in_loop(lambda:[
                CompetitionHome(bot,guild,user),PodiumView(bot,guild),
                RoundSignupLayout(bot,row,3),RoundActiveLayout(bot,row,3),
                RoundEndedLayout(row,[])
            ])
            self.assertTrue(all(isinstance(v,discord.ui.LayoutView) for v in views))
            # The /competition image is deliberately frameless and its
            # buttons are outside a Container to avoid Discord's grey card.
            self.assertIsInstance(views[0].children[0],discord.ui.MediaGallery)
            self.assertIsInstance(views[0].children[1],discord.ui.ActionRow)
            self.assertTrue(all(any(isinstance(c,discord.ui.Container)
                                    for c in v.children) for v in views[1:]))
            self.assertTrue(all(len(v.children)>=1 for v in views))
            s.close()
