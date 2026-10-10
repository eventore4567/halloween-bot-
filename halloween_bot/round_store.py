"""Persistent automatic Halloween Cup rounds and scheduler control plane.

All state transitions are atomic SQLite transactions; IDs are deduplicated.
Discord messages can be repaired after restarts from the persisted state.
"""
from __future__ import annotations
import time

INTERVALS = (30, 60, 120)
SIGNUP_WINDOWS = (10, 30)
PLAY_MINUTES = 10

class RoundStore:
    def __init__(self, store):
        self.store = store
        with store.transaction() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS round_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                role_id INTEGER,
                interval_min INTEGER NOT NULL DEFAULT 60,
                signup_min INTEGER NOT NULL DEFAULT 10,
                enabled INTEGER NOT NULL DEFAULT 0,
                next_at INTEGER NOT NULL DEFAULT 0,
                prize_label TEXT NOT NULL DEFAULT '',
                rules_url TEXT NOT NULL DEFAULT ''
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS competition_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('signup','active','finished','cancelled')),
                created_at INTEGER NOT NULL,
                signup_ends_at INTEGER NOT NULL,
                started_at INTEGER,
                ends_at INTEGER,
                finished_at INTEGER,
                signup_message_id INTEGER,
                challenge_message_id INTEGER
            )""")
            c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_open_round
                ON competition_rounds(guild_id)
                WHERE status IN ('signup','active')""")
            c.execute("""CREATE TABLE IF NOT EXISTS round_participants (
                round_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at INTEGER NOT NULL,
                PRIMARY KEY(round_id,user_id)
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS round_status_idx
                ON competition_rounds(status,signup_ends_at,ends_at)""")

    def _ensure(self, c, guild_id):
        c.execute(
            "INSERT OR IGNORE INTO round_config(guild_id) VALUES (?)",
            (guild_id,),
        )

    def config(self, guild_id):
        with self.store.transaction() as c:
            self._ensure(c, guild_id)
            return dict(c.execute(
                "SELECT * FROM round_config WHERE guild_id=?", (guild_id,)
            ).fetchone())

    def configure(self, guild_id, *, channel_id=None, role_id=None,
                  interval_min=None, signup_min=None, prize_label=None,
                  rules_url=None):
        allowed = {}
        if channel_id is not None:
            if not isinstance(channel_id, int) or channel_id <= 0:
                raise ValueError("Invalid channel")
            allowed["channel_id"] = channel_id
        if role_id is not None:
            if not isinstance(role_id, int) or role_id <= 0:
                raise ValueError("Invalid role")
            allowed["role_id"] = role_id
        if interval_min is not None:
            if interval_min not in INTERVALS:
                raise ValueError("Invalid interval")
            allowed["interval_min"] = interval_min
        if signup_min is not None:
            if signup_min not in SIGNUP_WINDOWS:
                raise ValueError("Invalid signup window")
            allowed["signup_min"] = signup_min
        if prize_label is not None:
            if len(prize_label) > 100:
                raise ValueError("Prize label is too long")
            allowed["prize_label"] = prize_label.strip()
        if rules_url is not None:
            from urllib.parse import urlparse
            url = rules_url.strip()
            if url and not (url.startswith("https://") and urlparse(url).hostname):
                raise ValueError("Rules must be an HTTPS URL")
            allowed["rules_url"] = url
        with self.store.transaction() as c:
            self._ensure(c, guild_id)
            if allowed:
                columns = ", ".join(f"{key}=?" for key in allowed)
                c.execute(
                    f"UPDATE round_config SET {columns} WHERE guild_id=?",
                    (*allowed.values(), guild_id),
                )
            return dict(c.execute(
                "SELECT * FROM round_config WHERE guild_id=?", (guild_id,)
            ).fetchone())

    def enable(self, guild_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.transaction() as c:
            self._ensure(c, guild_id)
            row = c.execute(
                "SELECT * FROM round_config WHERE guild_id=?", (guild_id,)
            ).fetchone()
            if not row["channel_id"] or not row["role_id"]:
                return "incomplete"
            if row["prize_label"] and not row["rules_url"]:
                return "rules_required"
            # A second click does not reset next_at and multiply announcements.
            c.execute(
                "UPDATE round_config SET enabled=1, "
                "next_at=CASE WHEN enabled=0 THEN ? ELSE next_at END "
                "WHERE guild_id=?", (now, guild_id)
            )
            return "enabled" if not row["enabled"] else "already_enabled"

    def suspend(self, guild_id):
        """Stop opening new rounds automatically once the season expires."""
        with self.store.transaction() as c:
            c.execute(
                "UPDATE round_config SET enabled=0,next_at=0 WHERE guild_id=?",
                (guild_id,),
            )

    def all_enabled(self):
        with self.store.lock:
            return [dict(row) for row in self.store.db.execute(
                "SELECT * FROM round_config WHERE enabled=1 AND channel_id IS NOT NULL "
                "AND role_id IS NOT NULL"
            ).fetchall()]

    def claim_due(self, now=None):
        now = int(time.time() if now is None else now)
        result = []
        with self.store.transaction() as c:
            rows = c.execute(
                "SELECT * FROM round_config WHERE enabled=1 AND next_at<=? "
                "AND channel_id IS NOT NULL AND role_id IS NOT NULL",
                (now,),
            ).fetchall()
            for row in rows:
                guild_id = row["guild_id"]
                exists = c.execute(
                    "SELECT 1 FROM competition_rounds WHERE guild_id=? "
                    "AND status IN ('signup','active') LIMIT 1",
                    (guild_id,),
                ).fetchone()
                if exists:
                    # Skip overlapping rounds; the next iteration can proceed.
                    c.execute(
                        "UPDATE round_config SET next_at=? WHERE guild_id=?",
                        (now + row["interval_min"]*60, guild_id),
                    )
                    continue
                deadline = now + row["signup_min"]*60
                c.execute(
                    """INSERT INTO competition_rounds
                    (guild_id,channel_id,role_id,status,created_at,signup_ends_at)
                    VALUES (?,?,?,'signup',?,?)""",
                    (guild_id,row["channel_id"],row["role_id"],now,deadline)
                )
                round_id = c.lastrowid
                c.execute(
                    "UPDATE round_config SET next_at=? WHERE guild_id=?",
                    (now+row["interval_min"]*60,guild_id)
                )
                result.append(round_id)
        return result

    def round(self, round_id):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM competition_rounds WHERE id=?", (round_id,)
            ).fetchone()
            return dict(row) if row else None

    def ongoing(self):
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT * FROM competition_rounds "
                "WHERE status IN ('signup','active') ORDER BY id"
            ).fetchall()
            return [dict(row) for row in rows]

    def current(self, guild_id):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM competition_rounds "
                "WHERE guild_id=? AND status IN ('signup','active') "
                "ORDER BY id DESC LIMIT 1", (guild_id,)
            ).fetchone()
            return dict(row) if row else None

    def bind(self, round_id, phase, message_id):
        column = {
            "signup": "signup_message_id",
            "active": "challenge_message_id",
        }.get(phase)
        if not column:
            raise ValueError("Unknown phase")
        with self.store.transaction() as c:
            c.execute(
                f"UPDATE competition_rounds SET {column}=? WHERE id=? AND status=?",
                (message_id,round_id,phase)
            )
            return c.rowcount == 1

    def join(self, round_id, guild_id, user_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.transaction() as c:
            row = c.execute(
                "SELECT * FROM competition_rounds WHERE id=? AND guild_id=?",
                (round_id,guild_id)
            ).fetchone()
            if not row or row["status"]!="signup" or now >= row["signup_ends_at"]:
                return "closed"
            import sqlite3
            try:
                c.execute(
                    "INSERT INTO round_participants VALUES (?,?,?)",
                    (round_id,user_id,now)
                )
            except sqlite3.IntegrityError:
                return "already_joined"
            return "joined"

    def count(self, round_id):
        with self.store.lock:
            return self.store.db.execute(
                "SELECT COUNT(*) FROM round_participants WHERE round_id=?",
                (round_id,)
            ).fetchone()[0]

    def check(self, guild_id, user_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM competition_rounds WHERE guild_id=? "
                "AND status IN ('signup','active') ORDER BY id DESC LIMIT 1",
                (guild_id,)
            ).fetchone()
            if not row:
                return "no_round", None
            item = dict(row)
            if row["status"]!="active":
                return "signup", item
            if now>=row["ends_at"]:
                return "expired", item
            joined = self.store.db.execute(
                "SELECT 1 FROM round_participants WHERE round_id=? AND user_id=?",
                (row["id"],user_id)
            ).fetchone()
            if not joined:
                return "not_joined", item
            return "ready", item

    def activate_due(self, now=None):
        now = int(time.time() if now is None else now)
        activated = []
        with self.store.transaction() as c:
            rows = c.execute(
                "SELECT id FROM competition_rounds "
                "WHERE status='signup' AND signup_ends_at<=?",
                (now,)
            ).fetchall()
            for row in rows:
                rid = row["id"]
                c.execute(
                    "UPDATE competition_rounds "
                    "SET status='active',started_at=?,ends_at=? "
                    "WHERE id=? AND status='signup'",
                    (now,now+PLAY_MINUTES*60,rid)
                )
                if c.rowcount:
                    activated.append(rid)
        return activated

    def finish_due(self, now=None):
        now = int(time.time() if now is None else now)
        finished = []
        with self.store.transaction() as c:
            rows = c.execute(
                "SELECT id FROM competition_rounds "
                "WHERE status='active' AND ends_at<=?", (now,)
            ).fetchall()
            for row in rows:
                c.execute(
                    "UPDATE competition_rounds SET status='finished',finished_at=? "
                    "WHERE id=? AND status='active'",
                    (now,row["id"])
                )
                if c.rowcount:
                    finished.append(row["id"])
        return finished

    def cancel(self, round_id):
        with self.store.transaction() as c:
            c.execute(
                "UPDATE competition_rounds SET status='cancelled' "
                "WHERE id=? AND status IN ('signup','active')", (round_id,)
            )

    def round_standings(self, round_id, limit=5):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM competition_rounds WHERE id=?", (round_id,)
            ).fetchone()
            if not row:
                return []
            participants = self.store.db.execute(
                """SELECT p.user_id,
                     COALESCE(SUM(a.points),0) AS score
                   FROM round_participants p
                   LEFT JOIN tournament_attempts a
                     ON a.guild_id=? AND a.user_id=p.user_id
                     AND a.started_at>=? AND a.started_at<?
                     AND a.outcome='correct'
                   WHERE p.round_id=?
                   GROUP BY p.user_id
                   ORDER BY score DESC, p.user_id ASC LIMIT ?""",
                (row["guild_id"],row["started_at"] or row["created_at"],
                 row["ends_at"] or 2147483647,round_id,limit)
            ).fetchall()
            return [dict(p) for p in participants]
