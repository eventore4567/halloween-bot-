"""SQLite persistence. Every balance change goes through one transaction."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS players(
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    candies INTEGER NOT NULL DEFAULT 0,
    earned INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    last_daily TEXT,
    title TEXT,
    theme TEXT NOT NULL DEFAULT 'orange',
    created REAL NOT NULL,
    PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS stats(
    guild_id INTEGER, user_id INTEGER, key TEXT, value INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, key));
CREATE TABLE IF NOT EXISTS counters(
    guild_id INTEGER, user_id INTEGER, day TEXT, key TEXT, value INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, day, key));
CREATE TABLE IF NOT EXISTS cooldowns(
    guild_id INTEGER, user_id INTEGER, key TEXT, until REAL,
    PRIMARY KEY (guild_id, user_id, key));
CREATE TABLE IF NOT EXISTS inventory(
    guild_id INTEGER, user_id INTEGER, item TEXT, qty INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, item));
CREATE TABLE IF NOT EXISTS effects(
    guild_id INTEGER, user_id INTEGER, key TEXT, until REAL,
    PRIMARY KEY (guild_id, user_id, key));
CREATE TABLE IF NOT EXISTS quiz_seen(
    guild_id INTEGER, user_id INTEGER, qid TEXT,
    PRIMARY KEY (guild_id, user_id, qid));
CREATE TABLE IF NOT EXISTS cards(
    guild_id INTEGER, user_id INTEGER, card TEXT, count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, card));
CREATE TABLE IF NOT EXISTS owned(
    guild_id INTEGER, user_id INTEGER, thing TEXT,
    PRIMARY KEY (guild_id, user_id, thing));
CREATE TABLE IF NOT EXISTS guilds(
    guild_id INTEGER PRIMARY KEY, drop_channel INTEGER, drops_on INTEGER NOT NULL DEFAULT 1,
    drop_every INTEGER NOT NULL DEFAULT 40);
CREATE TABLE IF NOT EXISTS ledger(
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    delta INTEGER, reason TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS players_rank ON players(guild_id, candies DESC);
"""


class NotEnough(Exception):
    """Raised when a player cannot pay."""


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    @contextmanager
    def tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def q(self, sql, *args):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def one(self, sql, *args):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    # ------------------------------------------------------------------ meta
    def meta_get(self, key, default=None):
        row = self.one("SELECT value FROM meta WHERE key=?", key)
        return json.loads(row["value"]) if row else default

    def meta_set(self, key, value):
        with self.tx() as db:
            db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))

    def meta_del(self, key):
        with self.tx() as db:
            db.execute("DELETE FROM meta WHERE key=?", (key,))

    def meta_prefix(self, prefix) -> dict:
        rows = self.q("SELECT key,value FROM meta WHERE key LIKE ?", prefix + "%")
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # --------------------------------------------------------------- players
    def _ensure(self, db, g, u):
        db.execute("INSERT OR IGNORE INTO players(guild_id,user_id,created) VALUES(?,?,?)", (g, u, time.time()))

    def player(self, g, u):
        with self.tx() as db:
            self._ensure(db, g, u)
            return dict(db.execute("SELECT * FROM players WHERE guild_id=? AND user_id=?", (g, u)).fetchone())

    def candies(self, g, u) -> int:
        row = self.one("SELECT candies FROM players WHERE guild_id=? AND user_id=?", g, u)
        return row["candies"] if row else 0

    def boosted(self, g, u, amount: int) -> int:
        """Apply the x2 luck potion to a positive gain."""
        if amount > 0 and self.effect_active(g, u, "luck"):
            return amount * 2
        return amount

    def add_candies(self, g, u, amount: int, reason: str, boost=True) -> int:
        """Credit (or debit with a negative amount). Returns the real delta."""
        if boost:
            amount = self.boosted(g, u, amount)
        with self.tx() as db:
            self._ensure(db, g, u)
            if amount < 0:
                cur = db.execute("UPDATE players SET candies=candies+? WHERE guild_id=? AND user_id=? AND candies>=?",
                                 (amount, g, u, -amount))
                if cur.rowcount == 0:
                    raise NotEnough()
            else:
                db.execute("UPDATE players SET candies=candies+?, earned=earned+? WHERE guild_id=? AND user_id=?",
                           (amount, amount, g, u))
            db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                       (g, u, amount, reason, time.time()))
        return amount

    def spend(self, g, u, amount: int, reason: str):
        return self.add_candies(g, u, -abs(amount), reason, boost=False)

    def transfer(self, g, src, dst, amount: int, reason="don"):
        with self.tx() as db:
            self._ensure(db, g, src)
            self._ensure(db, g, dst)
            cur = db.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                             (amount, g, src, amount))
            if cur.rowcount == 0:
                raise NotEnough()
            db.execute("UPDATE players SET candies=candies+? WHERE guild_id=? AND user_id=?", (amount, g, dst))
            db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                       (g, src, -amount, reason, time.time()))
            db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                       (g, dst, amount, reason, time.time()))

    def add_xp(self, g, u, amount: int):
        """Returns (old_level, new_level)."""
        if self.effect_active(g, u, "wisdom"):
            amount *= 2
        with self.tx() as db:
            self._ensure(db, g, u)
            old = db.execute("SELECT xp FROM players WHERE guild_id=? AND user_id=?", (g, u)).fetchone()["xp"]
            db.execute("UPDATE players SET xp=xp+? WHERE guild_id=? AND user_id=?", (amount, g, u))
        return config.level_from_xp(old)[0], config.level_from_xp(old + amount)[0]

    def set_field(self, g, u, field, value):
        assert field in {"title", "theme", "streak", "last_daily"}
        with self.tx() as db:
            self._ensure(db, g, u)
            db.execute(f"UPDATE players SET {field}=? WHERE guild_id=? AND user_id=?", (value, g, u))

    def claim_daily(self, g, u, day: str, yesterday: str):
        """Returns new streak, or None if already claimed today."""
        with self.tx() as db:
            self._ensure(db, g, u)
            row = db.execute("SELECT streak,last_daily FROM players WHERE guild_id=? AND user_id=?", (g, u)).fetchone()
            if row["last_daily"] == day:
                return None
            streak = row["streak"] + 1 if row["last_daily"] == yesterday else 1
            db.execute("UPDATE players SET streak=?, last_daily=? WHERE guild_id=? AND user_id=?", (streak, day, g, u))
            return streak

    # ----------------------------------------------------------------- stats
    def stat_add(self, g, u, key, amount=1):
        with self.tx() as db:
            db.execute("INSERT INTO stats(guild_id,user_id,key,value) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,key) DO UPDATE SET value=value+excluded.value",
                       (g, u, key, amount))

    def stat_max(self, g, u, key, value):
        with self.tx() as db:
            db.execute("INSERT INTO stats(guild_id,user_id,key,value) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,key) DO UPDATE SET value=MAX(value,excluded.value)",
                       (g, u, key, value))

    def stats(self, g, u) -> dict:
        return {r["key"]: r["value"] for r in self.q("SELECT key,value FROM stats WHERE guild_id=? AND user_id=?", g, u)}

    # -------------------------------------------------------------- counters
    def counter(self, g, u, key, day=None) -> int:
        row = self.one("SELECT value FROM counters WHERE guild_id=? AND user_id=? AND day=? AND key=?",
                       g, u, day or config.today(), key)
        return row["value"] if row else 0

    def bump(self, g, u, key, limit=None, amount=1, day=None) -> bool:
        """Increment a daily counter if it stays within ``limit``."""
        day = day or config.today()
        with self.tx() as db:
            row = db.execute("SELECT value FROM counters WHERE guild_id=? AND user_id=? AND day=? AND key=?",
                             (g, u, day, key)).fetchone()
            cur = row["value"] if row else 0
            if limit is not None and cur + amount > limit:
                return False
            db.execute("INSERT INTO counters(guild_id,user_id,day,key,value) VALUES(?,?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,day,key) DO UPDATE SET value=value+excluded.value",
                       (g, u, day, key, amount))
            return True

    def limit_for(self, g, u, game) -> int:
        base = config.LIMITS[game]
        if game == "quiz":
            base += self.counter(g, u, "quiz_bonus")
        return base

    def remaining(self, g, u, game) -> int:
        return max(0, self.limit_for(g, u, game) - self.counter(g, u, game))

    def use_play(self, g, u, game) -> bool:
        return self.bump(g, u, game, self.limit_for(g, u, game))

    # ------------------------------------------------------------- cooldowns
    def cooldown_left(self, g, u, key) -> float:
        row = self.one("SELECT until FROM cooldowns WHERE guild_id=? AND user_id=? AND key=?", g, u, key)
        return max(0.0, row["until"] - time.time()) if row else 0.0

    def set_cooldown(self, g, u, key, seconds):
        with self.tx() as db:
            db.execute("INSERT INTO cooldowns(guild_id,user_id,key,until) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,key) DO UPDATE SET until=excluded.until",
                       (g, u, key, time.time() + seconds))

    def take_cooldown(self, g, u, key, seconds) -> bool:
        with self.tx() as db:
            row = db.execute("SELECT until FROM cooldowns WHERE guild_id=? AND user_id=? AND key=?",
                             (g, u, key)).fetchone()
            if row and row["until"] > time.time():
                return False
            db.execute("INSERT INTO cooldowns(guild_id,user_id,key,until) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,key) DO UPDATE SET until=excluded.until",
                       (g, u, key, time.time() + seconds))
            return True

    # ------------------------------------------------------------- inventory
    def items(self, g, u) -> dict:
        return {r["item"]: r["qty"] for r in
                self.q("SELECT item,qty FROM inventory WHERE guild_id=? AND user_id=? AND qty>0", g, u)}

    def item_qty(self, g, u, item) -> int:
        row = self.one("SELECT qty FROM inventory WHERE guild_id=? AND user_id=? AND item=?", g, u, item)
        return row["qty"] if row else 0

    def give_item(self, g, u, item, qty=1):
        with self.tx() as db:
            db.execute("INSERT INTO inventory(guild_id,user_id,item,qty) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,item) DO UPDATE SET qty=qty+excluded.qty",
                       (g, u, item, qty))

    def use_item(self, g, u, item, qty=1) -> bool:
        with self.tx() as db:
            cur = db.execute("UPDATE inventory SET qty=qty-? WHERE guild_id=? AND user_id=? AND item=? AND qty>=?",
                             (qty, g, u, item, qty))
            return cur.rowcount > 0

    def buy(self, g, u, price, item=None, thing=None, reason="boutique"):
        """Atomic purchase: pay and receive the item (or permanent thing)."""
        with self.tx() as db:
            self._ensure(db, g, u)
            if thing and db.execute("SELECT 1 FROM owned WHERE guild_id=? AND user_id=? AND thing=?",
                                    (g, u, thing)).fetchone():
                raise ValueError("owned")
            cur = db.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                             (price, g, u, price))
            if cur.rowcount == 0:
                raise NotEnough()
            if item:
                db.execute("INSERT INTO inventory(guild_id,user_id,item,qty) VALUES(?,?,?,1) "
                           "ON CONFLICT(guild_id,user_id,item) DO UPDATE SET qty=qty+1", (g, u, item))
            if thing:
                db.execute("INSERT INTO owned(guild_id,user_id,thing) VALUES(?,?,?)", (g, u, thing))
            db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                       (g, u, -price, reason, time.time()))

    def unlock(self, g, u, thing) -> bool:
        """Grant a permanent thing; True only the first time."""
        with self.tx() as db:
            return db.execute("INSERT OR IGNORE INTO owned(guild_id,user_id,thing) VALUES(?,?,?)",
                              (g, u, thing)).rowcount > 0

    def owns(self, g, u, thing) -> bool:
        return self.one("SELECT 1 FROM owned WHERE guild_id=? AND user_id=? AND thing=?", g, u, thing) is not None

    def owned(self, g, u) -> set:
        return {r["thing"] for r in self.q("SELECT thing FROM owned WHERE guild_id=? AND user_id=?", g, u)}

    # --------------------------------------------------------------- effects
    def add_effect(self, g, u, key, seconds):
        """Start or extend a timed effect."""
        now = time.time()
        with self.tx() as db:
            row = db.execute("SELECT until FROM effects WHERE guild_id=? AND user_id=? AND key=?", (g, u, key)).fetchone()
            start = max(now, row["until"]) if row else now
            db.execute("INSERT INTO effects(guild_id,user_id,key,until) VALUES(?,?,?,?) "
                       "ON CONFLICT(guild_id,user_id,key) DO UPDATE SET until=excluded.until",
                       (g, u, key, start + seconds))
            return start + seconds

    def effect_active(self, g, u, key) -> bool:
        row = self.one("SELECT until FROM effects WHERE guild_id=? AND user_id=? AND key=?", g, u, key)
        return bool(row and row["until"] > time.time())

    def effects(self, g, u) -> dict:
        now = time.time()
        return {r["key"]: r["until"] for r in
                self.q("SELECT key,until FROM effects WHERE guild_id=? AND user_id=? AND until>?", g, u, now)}

    # ------------------------------------------------------------------ quiz
    def quiz_seen(self, g, u) -> set:
        return {r["qid"] for r in self.q("SELECT qid FROM quiz_seen WHERE guild_id=? AND user_id=?", g, u)}

    def mark_seen(self, g, u, qid):
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO quiz_seen(guild_id,user_id,qid) VALUES(?,?,?)", (g, u, qid))

    def forget_seen(self, g, u, qids):
        with self.tx() as db:
            db.executemany("DELETE FROM quiz_seen WHERE guild_id=? AND user_id=? AND qid=?",
                           [(g, u, q) for q in qids])

    # ----------------------------------------------------------------- cards
    def cards(self, g, u) -> dict:
        return {r["card"]: r["count"] for r in
                self.q("SELECT card,count FROM cards WHERE guild_id=? AND user_id=? AND count>0", g, u)}

    def add_card(self, g, u, card) -> int:
        with self.tx() as db:
            db.execute("INSERT INTO cards(guild_id,user_id,card,count) VALUES(?,?,?,1) "
                       "ON CONFLICT(guild_id,user_id,card) DO UPDATE SET count=count+1", (g, u, card))
            return db.execute("SELECT count FROM cards WHERE guild_id=? AND user_id=? AND card=?",
                              (g, u, card)).fetchone()[0]

    def trade(self, g, a, b, give: list[str], take: list[str], candies: int = 0) -> bool:
        """Atomic card swap: ``a`` gives ``give`` (+ ``candies``) to ``b`` and receives ``take``.

        Returns False (and changes nothing) if someone no longer owns what they promised.
        """
        from collections import Counter

        class _Abort(Exception):
            pass

        try:
            with self.tx() as db:
                for owner, cards in ((a, give), (b, take)):
                    for card, n in Counter(cards).items():
                        row = db.execute("SELECT count FROM cards WHERE guild_id=? AND user_id=? AND card=?",
                                         (g, owner, card)).fetchone()
                        if not row or row["count"] < n:
                            raise _Abort
                for src, dst, cards in ((a, b, give), (b, a, take)):
                    for card in cards:
                        db.execute("UPDATE cards SET count=count-1 WHERE guild_id=? AND user_id=? AND card=?",
                                   (g, src, card))
                        db.execute("INSERT INTO cards(guild_id,user_id,card,count) VALUES(?,?,?,1) "
                                   "ON CONFLICT(guild_id,user_id,card) DO UPDATE SET count=count+1", (g, dst, card))
                if candies:
                    self._ensure(db, g, a)
                    self._ensure(db, g, b)
                    cur = db.execute("UPDATE players SET candies=candies-? WHERE guild_id=? AND user_id=? AND candies>=?",
                                     (candies, g, a, candies))
                    if cur.rowcount == 0:
                        raise _Abort
                    db.execute("UPDATE players SET candies=candies+? WHERE guild_id=? AND user_id=?", (candies, g, b))
                    now = time.time()
                    db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                               (g, a, -candies, "echange", now))
                    db.execute("INSERT INTO ledger(guild_id,user_id,delta,reason,ts) VALUES(?,?,?,?,?)",
                               (g, b, candies, "echange", now))
        except _Abort:
            return False
        return True

    # ----------------------------------------------------------- leaderboard
    BOARDS = {
        "candies": "SELECT user_id, candies AS v FROM players WHERE guild_id=? AND candies>0 ORDER BY v DESC, user_id",
        "earned": "SELECT user_id, earned AS v FROM players WHERE guild_id=? AND earned>0 ORDER BY v DESC, user_id",
        "xp": "SELECT user_id, xp AS v FROM players WHERE guild_id=? AND xp>0 ORDER BY v DESC, user_id",
        "expedition": "SELECT user_id, value AS v FROM stats WHERE guild_id=? AND key='exp_win' AND value>0 "
                      "ORDER BY v DESC, user_id",
        "show": "SELECT user_id, value AS v FROM stats WHERE guild_id=? AND key='show_best' AND value>0 "
                "ORDER BY v DESC, user_id",
        "cards": "SELECT user_id, COUNT(*) AS v FROM cards WHERE guild_id=? AND count>0 GROUP BY user_id "
                 "ORDER BY v DESC, user_id",
        "quiz": "SELECT user_id, value AS v FROM stats WHERE guild_id=? AND key='quiz_right' AND value>0 "
                "ORDER BY v DESC, user_id",
        "duel": "SELECT user_id, value AS v FROM stats WHERE guild_id=? AND key='duel_win' AND value>0 "
                "ORDER BY v DESC, user_id",
        "fuite": "SELECT user_id, value AS v FROM stats WHERE guild_id=? AND key='run_best' AND value>0 "
                 "ORDER BY v DESC, user_id",
    }

    def board(self, g, kind, limit=10):
        return [(r["user_id"], r["v"]) for r in self.q(self.BOARDS[kind] + " LIMIT ?", g, limit)]

    def rank(self, g, u, kind):
        """(rank, total) with ties sharing the same rank; rank None when unranked."""
        rows = self.q(self.BOARDS[kind], g)
        total = len(rows)
        mine = next((r["v"] for r in rows if r["user_id"] == u), None)
        if mine is None:
            return None, total
        better = sum(1 for r in rows if r["v"] > mine)
        return better + 1, total

    # ---------------------------------------------------------------- guilds
    def guild(self, g) -> dict:
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO guilds(guild_id) VALUES(?)", (g,))
            return dict(db.execute("SELECT * FROM guilds WHERE guild_id=?", (g,)).fetchone())

    def guild_set(self, g, **fields):
        allowed = {"drop_channel", "drops_on", "drop_every"}
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO guilds(guild_id) VALUES(?)", (g,))
            for k, v in fields.items():
                assert k in allowed
                db.execute(f"UPDATE guilds SET {k}=? WHERE guild_id=?", (v, g))
