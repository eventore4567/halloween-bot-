"""Database integrity tests: no double-spend, isolated servers, persistent harvests."""
import tempfile
import threading
import unittest
from pathlib import Path

from halloween_bot.storage import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.tmp.name)/"tests.sqlite3"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_server_isolation(self):
        self.store.award(1,10,300)
        self.assertEqual(self.store.profile(1,10)["candies"],300)
        self.assertEqual(self.store.profile(2,10)["candies"],0)

    def test_daily_cooldown_atomic(self):
        self.assertEqual(self.store.cooldown(1,10,"daily",60,now=100),0)
        self.assertEqual(self.store.cooldown(1,10,"daily",60,now=101),59)
        self.assertEqual(self.store.cooldown(1,10,"daily",60,now=160),0)

    def test_shop_no_double_spend(self):
        self.store.award(1,10,100)
        self.assertTrue(self.store.buy(1,10,"hat",95))
        self.assertFalse(self.store.buy(1,10,"hat",95))
        self.assertEqual(self.store.inventory(1,10)[0]["quantity"],1)
        self.assertEqual(self.store.profile(1,10)["candies"],5)

    def test_gifts_do_not_mint_currency(self):
        self.store.award(1,10,100)
        self.assertFalse(self.store.gift(1,10,11,200))
        self.assertFalse(self.store.gift(1,10,10,10))
        self.assertTrue(self.store.gift(1,10,11,75))
        self.assertEqual(self.store.profile(1,10)["candies"],25)
        self.assertEqual(self.store.profile(1,11)["candies"],75)
        self.assertEqual(self.store.profile(1,11)["earned"],0)

    def test_event_awards_exactly_one_person(self):
        event=self.store.spawn(1,123,"ghost",180)
        self.assertIsNotNone(event)
        result=[]
        def claim(i):
            result.append(self.store.claim(event,1,i))
        threads=[threading.Thread(target=claim,args=(i,)) for i in range(25)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(result.count(180),1)
        self.assertEqual(sum(self.store.profile(1,i)["candies"] for i in range(25)),180)

    def test_expired_event_cannot_be_claimed(self):
        event=self.store.spawn(1,123,"ghost",140,ttl=-1)
        self.assertEqual(self.store.claim(event,1,10),0)

    def test_farm_harvest_only_once(self):
        self.assertEqual(self.store.plant(1,10,"citrouille",now=1000),"planted")
        self.assertEqual(self.store.plant(1,10,"citrouille",now=1001),"occupied")
        self.assertEqual(self.store.harvest(1,10,now=1005)["status"],"growing")
        result=self.store.harvest(1,10,now=1600)
        self.assertEqual(result["status"],"harvested")
        self.assertEqual(self.store.harvest(1,10,now=1601)["status"],"empty")
        self.assertEqual(self.store.profile(1,10)["candies"],result["amount"])
        self.assertEqual(self.store.profile(1,10)["harvests"],1)

    def test_farm_paid_seed_and_upgrade(self):
        self.assertEqual(self.store.plant(1,10,"maudite",now=100),"poor")
        self.store.award(1,10,1000)
        self.assertEqual(self.store.plant(1,10,"maudite",now=100),"planted")
        self.assertEqual(self.store.profile(1,10)["candies"],860)
        self.assertEqual(self.store.upgrade_farm(1,10),("upgraded",2))
        self.assertEqual(self.store.profile(1,10)["candies"],410)

    def test_farm_isolation(self):
        self.store.plant(1,10,"citrouille",now=100)
        self.assertIsNone(self.store.farm(2,10)["crop"])

    def test_rankings(self):
        self.store.award(1,10,80,ghosts=2)
        self.store.award(1,11,120,ghosts=1)
        self.assertEqual(self.store.ranking(1,"candies")[0]["user_id"],11)
        self.assertEqual(self.store.ranking(1,"ghosts")[0]["user_id"],10)
        self.assertEqual(self.store.position(1,10),2)


if __name__=="__main__":
    unittest.main()
