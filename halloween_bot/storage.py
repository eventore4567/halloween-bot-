"""Persistent and transactional economy for Halloween Bot."""
from __future__ import annotations

import random
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

STATS = {"ghosts", "quizzes", "duel_wins", "duel_losses", "boss_damage",
         "events_won", "pumpkins", "harvests", "expeditions"}
CROPS = {
    "citrouille": ("🎃 Citrouille", 0, 8 * 60, 65, 115),
    "spectrale": ("👻 Citrouille spectrale", 45, 15 * 60, 135, 210),
    "maudite": ("💀 Citrouille maudite", 140, 30 * 60, 290, 420),
}


class Store:
    def __init__(self, filename="data/halloween.sqlite3"):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=10000")
        self.lock = threading.RLock()
        with self.transaction() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS players (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                candies INTEGER NOT NULL DEFAULT 0,
                earned INTEGER NOT NULL DEFAULT 0,
                ghosts INTEGER NOT NULL DEFAULT 0,
                quizzes INTEGER NOT NULL DEFAULT 0,
                duel_wins INTEGER NOT NULL DEFAULT 0,
                duel_losses INTEGER NOT NULL DEFAULT 0,
                boss_damage INTEGER NOT NULL DEFAULT 0,
                events_won INTEGER NOT NULL DEFAULT 0,
                pumpkins INTEGER NOT NULL DEFAULT 0,
                harvests INTEGER NOT NULL DEFAULT 0,
                expeditions INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id,user_id))""")
            c.execute("""CREATE TABLE IF NOT EXISTS cooldowns (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                action TEXT NOT NULL, ready_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id,user_id,action))""")
            c.execute("""CREATE TABLE IF NOT EXISTS inventory (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                item TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id,user_id,item))""")
            c.execute("""CREATE TABLE IF NOT EXISTS farms (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                crop TEXT, ready_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id,user_id))""")
            c.execute("""CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                event_channel INTEGER NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
                message_id INTEGER, kind TEXT NOT NULL,
                reward INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                winner_id INTEGER, closed INTEGER NOT NULL DEFAULT 0)""")

    @contextmanager
    def transaction(self):
        with self.lock:
            c = self.db.cursor()
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
            except BaseException:
                self.db.rollback()
                raise
            else:
                self.db.commit()
            finally:
                c.close()

    @staticmethod
    def ensure(c, guild_id, user_id):
        c.execute("INSERT OR IGNORE INTO players (guild_id,user_id) VALUES (?,?)",
                  (guild_id,user_id))

    def profile(self, guild_id, user_id):
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            return dict(c.execute(
                "SELECT * FROM players WHERE guild_id=? AND user_id=?",
                (guild_id,user_id)).fetchone())

    def award(self, guild_id, user_id, candies=0, **stats):
        if not isinstance(candies,int) or abs(candies)>1_000_000:
            raise ValueError("Invalid award")
        if not set(stats) <= STATS or any(not isinstance(v,int) or v<0 for v in stats.values()):
            raise ValueError("Invalid statistics")
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            c.execute("UPDATE players SET candies=MAX(0,candies+?),earned=earned+? "
                      "WHERE guild_id=? AND user_id=?",
                      (candies,max(0,candies),guild_id,user_id))
            for stat,amount in stats.items():
                c.execute(f"UPDATE players SET {stat}={stat}+? WHERE guild_id=? AND user_id=?",
                          (amount,guild_id,user_id))
            return dict(c.execute("SELECT * FROM players WHERE guild_id=? AND user_id=?",
                                  (guild_id,user_id)).fetchone())

    def cooldown(self, guild_id, user_id, action, duration, now=None):
        now = int(time.time() if now is None else now)
        with self.transaction() as c:
            row = c.execute("SELECT ready_at FROM cooldowns WHERE guild_id=? AND user_id=? AND action=?",
                            (guild_id,user_id,action)).fetchone()
            if row and row["ready_at"] > now:
                return row["ready_at"] - now
            c.execute("""INSERT INTO cooldowns VALUES (?,?,?,?)
                ON CONFLICT(guild_id,user_id,action) DO UPDATE SET ready_at=excluded.ready_at""",
                      (guild_id,user_id,action,now+duration))
            return 0

    def gift(self, guild_id, sender, target, amount):
        if sender==target or not isinstance(amount,int) or not 1<=amount<=10000:
            return False
        with self.transaction() as c:
            self.ensure(c,guild_id,sender)
            self.ensure(c,guild_id,target)
            c.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                      (amount,guild_id,sender,amount))
            if c.rowcount != 1:
                return False
            c.execute("UPDATE players SET candies=candies+? WHERE guild_id=? AND user_id=?",
                      (amount,guild_id,target))
            return True

    def buy(self, guild_id, user_id, item, price):
        if not 0<=price<=100000:
            return False
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            c.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                      (price,guild_id,user_id,price))
            if c.rowcount!=1:
                return False
            c.execute("""INSERT INTO inventory VALUES (?,?,?,1)
                ON CONFLICT(guild_id,user_id,item) DO UPDATE SET quantity=quantity+1""",
                      (guild_id,user_id,item))
            return True

    def inventory(self,guild_id,user_id):
        with self.lock:
            return [dict(x) for x in self.db.execute(
                "SELECT item,quantity FROM inventory WHERE guild_id=? AND user_id=? ORDER BY item",
                (guild_id,user_id)).fetchall()]

    def ranking(self,guild_id,stat="candies",limit=10):
        if stat not in {"candies","ghosts","duel_wins","earned","harvests","expeditions"}:
            raise ValueError("Invalid ranking")
        with self.lock:
            return [dict(x) for x in self.db.execute(
                f"SELECT user_id,{stat} AS score FROM players WHERE guild_id=? "
                f"ORDER BY {stat} DESC,earned DESC,user_id ASC LIMIT ?",
                (guild_id,limit)).fetchall()]

    def position(self,guild_id,user_id):
        with self.lock:
            rows=self.db.execute(
                "SELECT user_id FROM players WHERE guild_id=? ORDER BY candies DESC,earned DESC,user_id ASC",
                (guild_id,)).fetchall()
        return next((i for i,row in enumerate(rows,1) if row["user_id"]==user_id),0)

    def farm(self,guild_id,user_id):
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            c.execute("INSERT OR IGNORE INTO farms(guild_id,user_id) VALUES (?,?)",
                      (guild_id,user_id))
            return dict(c.execute(
                "SELECT * FROM farms WHERE guild_id=? AND user_id=?",
                (guild_id,user_id)).fetchone())

    def plant(self,guild_id,user_id,crop,now=None):
        if crop not in CROPS:
            return "unknown"
        now=int(time.time() if now is None else now)
        cost=CROPS[crop][1]
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            c.execute("INSERT OR IGNORE INTO farms(guild_id,user_id) VALUES (?,?)",
                      (guild_id,user_id))
            row=c.execute("SELECT crop FROM farms WHERE guild_id=? AND user_id=?",
                          (guild_id,user_id)).fetchone()
            if row["crop"]:
                return "occupied"
            c.execute("UPDATE players SET candies=candies-? "
                      "WHERE guild_id=? AND user_id=? AND candies>=?",
                      (cost,guild_id,user_id,cost))
            if c.rowcount!=1:
                return "poor"
            c.execute("UPDATE farms SET crop=?,ready_at=? WHERE guild_id=? AND user_id=?",
                      (crop,now+CROPS[crop][2],guild_id,user_id))
            return "planted"

    def harvest(self,guild_id,user_id,now=None):
        now=int(time.time() if now is None else now)
        with self.transaction() as c:
            row=c.execute("SELECT crop,ready_at,level FROM farms WHERE guild_id=? AND user_id=?",
                          (guild_id,user_id)).fetchone()
            if not row or row["crop"] is None:
                return {"status":"empty"}
            if row["ready_at"]>now:
                return {"status":"growing","seconds":row["ready_at"]-now}
            crop=row["crop"]
            low,high=CROPS[crop][3:]
            amount=int(random.randint(low,high)*(1+0.15*(row["level"]-1)))
            self.ensure(c,guild_id,user_id)
            c.execute("UPDATE players SET candies=candies+?,earned=earned+?,harvests=harvests+1 "
                      "WHERE guild_id=? AND user_id=?",
                      (amount,amount,guild_id,user_id))
            c.execute("UPDATE farms SET crop=NULL,ready_at=0 WHERE guild_id=? AND user_id=?",
                      (guild_id,user_id))
            return {"status":"harvested","amount":amount,"crop":crop}

    def upgrade_farm(self,guild_id,user_id):
        with self.transaction() as c:
            self.ensure(c,guild_id,user_id)
            c.execute("INSERT OR IGNORE INTO farms(guild_id,user_id) VALUES (?,?)",
                      (guild_id,user_id))
            row=c.execute("SELECT level FROM farms WHERE guild_id=? AND user_id=?",
                          (guild_id,user_id)).fetchone()
            level=row["level"]
            if level>=5:
                return "max",level
            price=level*450
            c.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                      (price,guild_id,user_id,price))
            if c.rowcount!=1:
                return "poor",price
            c.execute("UPDATE farms SET level=level+1 WHERE guild_id=? AND user_id=?",
                      (guild_id,user_id))
            return "upgraded",level+1

    def set_channel(self,guild_id,channel_id):
        with self.transaction() as c:
            c.execute("""INSERT INTO settings VALUES (?,?)
                ON CONFLICT(guild_id) DO UPDATE SET event_channel=excluded.event_channel""",
                      (guild_id,channel_id))

    def channels(self):
        with self.lock:
            return [dict(x) for x in self.db.execute("SELECT * FROM settings").fetchall()]

    def configured_channel(self,guild_id):
        with self.lock:
            row=self.db.execute("SELECT event_channel FROM settings WHERE guild_id=?",
                                (guild_id,)).fetchone()
            return row["event_channel"] if row else None

    def spawn(self,guild_id,channel_id,kind,reward,ttl=180,now=None):
        now=int(time.time() if now is None else now)
        with self.transaction() as c:
            c.execute("UPDATE events SET closed=1 WHERE closed=0 AND expires_at<=?",(now,))
            if c.execute("SELECT 1 FROM events WHERE guild_id=? AND closed=0 LIMIT 1",
                         (guild_id,)).fetchone():
                return None
            c.execute("INSERT INTO events(guild_id,channel_id,kind,reward,expires_at) VALUES (?,?,?,?,?)",
                      (guild_id,channel_id,kind,reward,now+ttl))
            return c.lastrowid

    def event_message(self,event_id,message_id):
        with self.transaction() as c:
            c.execute("UPDATE events SET message_id=? WHERE id=?",(message_id,event_id))

    def close_event(self,event_id):
        with self.transaction() as c:
            c.execute("UPDATE events SET closed=1 WHERE id=?",(event_id,))

    def pending_events(self,now=None):
        now=int(time.time() if now is None else now)
        with self.lock:
            return [dict(x) for x in self.db.execute(
                "SELECT * FROM events WHERE closed=0 AND expires_at>? AND message_id IS NOT NULL",
                (now,)).fetchall()]

    def expired_events(self,now=None):
        now=int(time.time() if now is None else now)
        with self.transaction() as c:
            rows=[dict(x) for x in c.execute(
                "SELECT * FROM events WHERE closed=0 AND expires_at<=?",(now,)).fetchall()]
            c.execute("UPDATE events SET closed=1 WHERE closed=0 AND expires_at<=?",(now,))
            return rows

    def claim(self,event_id,guild_id,user_id,now=None):
        now=int(time.time() if now is None else now)
        with self.transaction() as c:
            row=c.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
            if not row or row["guild_id"]!=guild_id or row["closed"] or row["expires_at"]<=now:
                return 0
            c.execute("UPDATE events SET closed=1,winner_id=? WHERE id=?",(user_id,event_id))
            self.ensure(c,guild_id,user_id)
            c.execute("UPDATE players SET candies=candies+?,earned=earned+?,events_won=events_won+1 "
                      "WHERE guild_id=? AND user_id=?",
                      (row["reward"],row["reward"],guild_id,user_id))
            return row["reward"]

    def close(self):
        with self.lock:
            self.db.close()
