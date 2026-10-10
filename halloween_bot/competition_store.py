"""Skill-based Halloween tournament: persistent, transactional, separately audited.

No candy RNG, gifts, premium items, purchases or chance games award tournament
points. Only correct answers to individually generated daily puzzles score.

This module does not settle or pay real-world prizes. The organizer must verify
eligibility, suspected abuse and ties before declaring any prize winner.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

MODES = {
    "calcul": {"title": "🔮 L'alchimie des nombres", "points": 100, "emoji": "🔮"},
    "mot": {"title": "📜 Les mots maudits", "points": 130, "emoji": "📜"},
    "code": {"title": "🗝️ Le code de la crypte", "points": 160, "emoji": "🗝️"},
}
MAX_TIME = 100  # seconds per challenge
MAX_SEASON_DAYS = 62
WORDS = (
    "citrouille", "cimetiere", "fantome", "sorcellerie", "vampire",
    "araignee", "monstre", "bougie", "cercueil", "chaudron",
    "squelette", "malediction", "chauvesouris", "momie", "manoir",
    "spectre", "creature", "lanterne", "terreur", "balai",
    "brume", "magie", "zombie", "catacombe", "cryptogramme",
    "corbeau", "ombre", "citadelle", "potion", "loup",
)

def normalize(text: str) -> str:
    """Normalize benign player input, without relying on casing or accents."""
    stripped = unicodedata.normalize("NFKD", text.casefold().strip())
    return "".join(c for c in stripped if not unicodedata.combining(c) and not c.isspace())

def calendar_day(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")

def season_label(now: int) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%d-%H%M%S")

def division(points: int) -> tuple[str, int, str]:
    if points >= 4500:
        return "👑 Légende", 4500, "legend"
    if points >= 2200:
        return "💎 Diamant", 4500, "diamond"
    if points >= 950:
        return "🥇 Or", 2200, "gold"
    if points >= 350:
        return "🥈 Argent", 950, "silver"
    return "🥉 Bronze", 350, "bronze"

def generate_puzzle(mode: str) -> tuple[str, str]:
    """Different randomized puzzles for different users; no shared daily answer."""
    if mode not in MODES:
        raise ValueError("Unknown mode")
    randomizer = secrets.SystemRandom()
    if mode == "calcul":
        a = randomizer.randint(13, 49)
        b = randomizer.randint(3, 12)
        c = randomizer.randint(7, 39)
        if randomizer.choice((True, False)):
            return (
                f"Le sorcier mélange **{a} potions** dans chacun de "
                f"**{b} chaudrons**, puis en perd **{c}**.\n\n"
                "Combien de potions lui reste-t-il ?",
                str(a * b - c),
            )
        return (
            f"Une sorcière a **{a} bonbons**, reçoit **{b} sacs de {c}** "
            "bonbons puis partage sa réserve en **2 paniers**.\n\n"
            "Quel est le **total avant le partage** ?",
            str(a + b * c),
        )
    if mode == "mot":
        word = randomizer.choice(WORDS)
        letters = list(word)
        for _ in range(8):
            randomizer.shuffle(letters)
            if "".join(letters) != word:
                break
        return (
            "Réassemble ce mot du grimoire :\n\n"
            f"**{' · '.join(letter.upper() for letter in letters)}**\n\n"
            "Écris le mot complet sans espaces.",
            word,
        )
    a = randomizer.randint(5, 20)
    b = randomizer.randint(3, 17)
    c = randomizer.randint(2, 8)
    return (
        "Dans la crypte, les glyphes portent des valeurs secrètes.\n\n"
        f"🦇 Une chauve-souris vaut **{a}**.\n"
        f"👻 Un fantôme vaut **{b} de plus** qu'une chauve-souris.\n"
        f"💀 Un crâne vaut **{c} de moins** qu'un fantôme.\n\n"
        "Calcule la valeur de **🦇 + 👻 + 💀**.",
        str(a + (a + b) + (a + b - c)),
    )

class Competition:
    """Persistence layer composing the existing Store and its serial write lock."""

    def __init__(self, store):
        self.store = store
        with store.transaction() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS tournament_seasons (
                guild_id INTEGER NOT NULL,
                season_id TEXT NOT NULL,
                title TEXT NOT NULL,
                begins_at INTEGER NOT NULL,
                ends_at INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','closed')),
                prize_label TEXT NOT NULL DEFAULT '',
                rules_url TEXT NOT NULL DEFAULT '',
                organizer_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                closed_at INTEGER,
                PRIMARY KEY(guild_id,season_id)
            )""")
            c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_tournament
                ON tournament_seasons(guild_id) WHERE status='active'""")
            c.execute("""CREATE TABLE IF NOT EXISTS tournament_entries (
                guild_id INTEGER NOT NULL,
                season_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at INTEGER NOT NULL,
                score INTEGER NOT NULL DEFAULT 0 CHECK(score>=0),
                solved INTEGER NOT NULL DEFAULT 0 CHECK(solved>=0),
                PRIMARY KEY(guild_id,season_id,user_id)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS tournament_attempts (
                attempt_id TEXT NOT NULL PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                season_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                utc_day TEXT NOT NULL,
                mode TEXT NOT NULL,
                puzzle TEXT NOT NULL,
                answer_salt TEXT NOT NULL,
                answer_digest TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                finished_at INTEGER,
                outcome TEXT NOT NULL DEFAULT 'pending'
                    CHECK(outcome IN ('pending','correct','incorrect','expired')),
                points INTEGER NOT NULL DEFAULT 0,
                UNIQUE(guild_id,season_id,user_id,utc_day,mode)
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS tournament_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT NOT NULL UNIQUE,
                guild_id INTEGER NOT NULL,
                season_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                points INTEGER NOT NULL,
                awarded_at INTEGER NOT NULL
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS tournament_leader_idx
                ON tournament_entries(guild_id,season_id,score DESC)""")
            c.execute("""CREATE INDEX IF NOT EXISTS tournament_audit_idx
                ON tournament_attempts(guild_id,season_id,started_at DESC)""")

    @staticmethod
    def _latest(c, guild_id):
        return c.execute(
            "SELECT * FROM tournament_seasons WHERE guild_id=? "
            "ORDER BY created_at DESC,season_id DESC LIMIT 1",
            (guild_id,),
        ).fetchone()

    @staticmethod
    def _expire(c, guild_id, now):
        c.execute(
            "UPDATE tournament_seasons SET status='closed',closed_at=ends_at "
            "WHERE guild_id=? AND status='active' AND ends_at<=?",
            (guild_id, now),
        )

    def season(self, guild_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.transaction() as c:
            self._expire(c, guild_id, now)
            row = self._latest(c, guild_id)
            return dict(row) if row else None

    def start(self, guild_id, organizer_id, ends_at, *, prize_label="",
              rules_url="", title="Halloween Cup", now=None):
        now = int(time.time() if now is None else now)
        ends_at = int(ends_at)
        if not (now + 3600 < ends_at <= now + MAX_SEASON_DAYS * 86400):
            return {"status": "bad_date"}
        prize_label = prize_label.strip()[:100]
        rules_url = rules_url.strip()
        # Real prizes must have an organizer-published rulebook before launch.
        if prize_label and not (rules_url.startswith("https://")
                                and urlparse(rules_url).hostname):
            return {"status": "rules_required"}
        with self.store.transaction() as c:
            self._expire(c, guild_id, now)
            if c.execute(
                "SELECT 1 FROM tournament_seasons "
                "WHERE guild_id=? AND status='active'", (guild_id,)
            ).fetchone():
                return {"status": "already_running"}
            season_id = season_label(now) + "-" + secrets.token_hex(3)
            c.execute(
                """INSERT INTO tournament_seasons
                (guild_id,season_id,title,begins_at,ends_at,status,
                 prize_label,rules_url,organizer_id,created_at)
                VALUES (?,?,?,?,?,'active',?,?,?,?)""",
                (guild_id, season_id, title[:70], now, ends_at,
                 prize_label, rules_url, organizer_id, now),
            )
            return {"status": "started", "season_id": season_id}

    def close(self, guild_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.transaction() as c:
            c.execute(
                "UPDATE tournament_seasons SET status='closed',closed_at=? "
                "WHERE guild_id=? AND status='active'", (now, guild_id)
            )
            return c.rowcount > 0

    def join(self, guild_id, user_id, now=None):
        now = int(time.time() if now is None else now)
        with self.store.transaction() as c:
            self._expire(c, guild_id, now)
            season = self._latest(c, guild_id)
            if not season or season["status"] != "active" or now < season["begins_at"]:
                return "closed"
            if c.execute(
                "SELECT 1 FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? AND user_id=?",
                (guild_id, season["season_id"], user_id),
            ).fetchone():
                return "joined"
            c.execute(
                "INSERT INTO tournament_entries(guild_id,season_id,user_id,joined_at) "
                "VALUES (?,?,?,?)",
                (guild_id, season["season_id"], user_id, now),
            )
            return "welcome"

    def entry(self, guild_id, user_id, now=None):
        season = self.season(guild_id, now)
        if not season:
            return None
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? AND user_id=?",
                (guild_id,season["season_id"],user_id),
            ).fetchone()
            return dict(row) if row else None

    def remaining_modes(self, guild_id, user_id, now=None):
        now = int(time.time() if now is None else now)
        season = self.season(guild_id, now)
        if not season:
            return []
        with self.store.lock:
            used = {
                r["mode"] for r in self.store.db.execute(
                    "SELECT mode FROM tournament_attempts "
                    "WHERE guild_id=? AND season_id=? AND user_id=? AND utc_day=?",
                    (guild_id, season["season_id"], user_id, calendar_day(now)),
                )
            }
        return [mode for mode in MODES if mode not in used]

    def issue(self, guild_id, user_id, mode, puzzle, answer, now=None):
        now = int(time.time() if now is None else now)
        if mode not in MODES or not puzzle or not answer:
            return {"status": "invalid"}
        salt = secrets.token_hex(16)
        attempt_id = secrets.token_urlsafe(18)
        digest = hashlib.sha256(
            (salt + "|" + normalize(answer)).encode("utf-8")
        ).hexdigest()
        with self.store.transaction() as c:
            self._expire(c, guild_id, now)
            season = self._latest(c, guild_id)
            if not season or season["status"] != "active":
                return {"status": "closed"}
            if not c.execute(
                "SELECT 1 FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? AND user_id=?",
                (guild_id, season["season_id"], user_id),
            ).fetchone():
                return {"status": "join_first"}
            if c.execute(
                "SELECT 1 FROM tournament_attempts "
                "WHERE guild_id=? AND season_id=? AND user_id=? "
                "AND utc_day=? AND mode=?",
                (guild_id, season["season_id"], user_id,
                 calendar_day(now), mode),
            ).fetchone():
                return {"status": "already_today"}
            deadline = min(now + MAX_TIME, season["ends_at"])
            if deadline <= now:
                return {"status": "closed"}
            c.execute(
                """INSERT INTO tournament_attempts
                (attempt_id,guild_id,season_id,user_id,utc_day,mode,puzzle,
                 answer_salt,answer_digest,started_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (attempt_id, guild_id, season["season_id"], user_id,
                 calendar_day(now), mode, puzzle, salt, digest, now, deadline),
            )
            return {"status": "issued", "attempt_id": attempt_id,
                    "expires_at": deadline, "puzzle": puzzle,
                    "mode": mode, "points": MODES[mode]["points"]}

    def answer(self, attempt_id, guild_id, user_id, submitted, now=None):
        now = int(time.time() if now is None else now)
        submitted = str(submitted)[:120]
        with self.store.transaction() as c:
            row = c.execute(
                "SELECT * FROM tournament_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if not row or row["guild_id"] != guild_id or row["user_id"] != user_id:
                return {"status": "forbidden", "points": 0}
            if row["outcome"] != "pending":
                return {"status": "used", "points": 0}
            self._expire(c, guild_id, now)
            season = c.execute(
                "SELECT status,ends_at FROM tournament_seasons "
                "WHERE guild_id=? AND season_id=?",
                (guild_id,row["season_id"]),
            ).fetchone()
            if (now > row["expires_at"] or not season or
                season["status"] != "active" or now >= season["ends_at"]):
                c.execute(
                    "UPDATE tournament_attempts SET outcome='expired',finished_at=? "
                    "WHERE attempt_id=?", (now, attempt_id)
                )
                return {"status": "expired", "points": 0}
            digest = hashlib.sha256(
                (row["answer_salt"] + "|" + normalize(submitted)).encode("utf-8")
            ).hexdigest()
            correct = hmac.compare_digest(digest, row["answer_digest"])
            points = MODES[row["mode"]]["points"] if correct else 0
            c.execute(
                "UPDATE tournament_attempts SET outcome=?,finished_at=?,points=? "
                "WHERE attempt_id=?",
                ("correct" if correct else "incorrect", now, points, attempt_id),
            )
            if correct:
                c.execute(
                    "UPDATE tournament_entries SET score=score+?,solved=solved+1 "
                    "WHERE guild_id=? AND season_id=? AND user_id=?",
                    (points,guild_id,row["season_id"],user_id),
                )
                c.execute(
                    "INSERT INTO tournament_awards "
                    "(attempt_id,guild_id,season_id,user_id,mode,points,awarded_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (attempt_id,guild_id,row["season_id"],user_id,row["mode"],points,now),
                )
            return {"status": "correct" if correct else "incorrect",
                    "points": points, "mode": row["mode"]}

    def standings(self, guild_id, limit=10, now=None):
        season = self.season(guild_id, now)
        if not season:
            return []
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT user_id,score,solved FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? "
                "ORDER BY score DESC,user_id ASC LIMIT ?",
                (guild_id,season["season_id"],limit),
            ).fetchall()
        output, prior, place = [], None, 0
        for index, row in enumerate(rows, 1):
            if row["score"] != prior:
                place = index
            output.append({**dict(row), "place": place})
            prior = row["score"]
        return output

    def position(self, guild_id, user_id, now=None):
        season = self.season(guild_id, now)
        if not season:
            return None
        with self.store.lock:
            player = self.store.db.execute(
                "SELECT score,solved FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? AND user_id=?",
                (guild_id,season["season_id"],user_id),
            ).fetchone()
            if not player:
                return None
            above = self.store.db.execute(
                "SELECT COUNT(*) AS n FROM tournament_entries "
                "WHERE guild_id=? AND season_id=? AND score>?",
                (guild_id,season["season_id"],player["score"]),
            ).fetchone()["n"]
            count = self.store.db.execute(
                "SELECT COUNT(*) AS n FROM tournament_entries "
                "WHERE guild_id=? AND season_id=?",
                (guild_id,season["season_id"]),
            ).fetchone()["n"]
            return {**dict(player), "place": above+1, "participants": count}

    def audit(self, guild_id, limit=5000, now=None):
        """Read-only log for an admin's manual eligibility and abuse review."""
        season = self.season(guild_id, now)
        if not season:
            return [], None
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT user_id,mode,utc_day,started_at,finished_at,outcome,points "
                "FROM tournament_attempts WHERE guild_id=? AND season_id=? "
                "ORDER BY started_at ASC,attempt_id ASC LIMIT ?",
                (guild_id,season["season_id"],limit),
            ).fetchall()
        return [dict(row) for row in rows], season
