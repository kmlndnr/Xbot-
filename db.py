import sqlite3
from datetime import datetime

DB_PATH = "drafts.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT NOT NULL UNIQUE,
                author_username TEXT,
                original_text TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                context_analysis TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                source TEXT NOT NULL DEFAULT 'mention',
                sentiment TEXT DEFAULT 'neutral',
                account_name TEXT DEFAULT 'main',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_tweets (
                tweet_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dm_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dm_id TEXT NOT NULL UNIQUE,
                sender_id TEXT NOT NULL,
                sender_username TEXT,
                original_text TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                context_analysis TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_dms (
                dm_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                account_name TEXT DEFAULT 'main',
                posted_tweet_id TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS known_followers (
                follower_id TEXT NOT NULL,
                account_name TEXT NOT NULL DEFAULT 'main',
                username TEXT,
                followed_at TEXT NOT NULL,
                welcomed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (follower_id, account_name)
            )
        """)
        conn.commit()
        _migrate(conn)


def _migrate(conn):
    """Fügt neue Spalten zu bestehenden Tabellen hinzu (idempotent)."""
    migrations = [
        ("drafts", "sentiment", "TEXT DEFAULT 'neutral'"),
        ("drafts", "account_name", "TEXT DEFAULT 'main'"),
    ]
    for table, column, definition in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.commit()
        except Exception:
            pass


# ── Mentions / Drafts ──────────────────────────────────────────────────────────

def save_draft(tweet_id: str, author_username: str, original_text: str,
               draft_text: str, context_analysis: str,
               source: str = "mention", sentiment: str = "neutral",
               account_name: str = "main") -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO drafts
                (tweet_id, author_username, original_text, draft_text,
                 context_analysis, status, source, sentiment, account_name,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (tweet_id, author_username, original_text, draft_text,
              context_analysis, source, sentiment, account_name, now, now))
        conn.commit()
        return cursor.lastrowid


def get_pending_drafts() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()


def get_all_drafts(limit: int = 50) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


def update_draft_status(draft_id: int, status: str, new_text: str | None = None):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        if new_text is not None:
            conn.execute(
                "UPDATE drafts SET status=?, draft_text=?, updated_at=? WHERE id=?",
                (status, new_text, now, draft_id)
            )
        else:
            conn.execute(
                "UPDATE drafts SET status=?, updated_at=? WHERE id=?",
                (status, now, draft_id)
            )
        conn.commit()


def mark_tweet_processed(tweet_id: str):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_tweets (tweet_id, processed_at) VALUES (?,?)",
            (tweet_id, now)
        )
        conn.commit()


def is_tweet_processed(tweet_id: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM processed_tweets WHERE tweet_id=?", (tweet_id,)
        ).fetchone() is not None


def get_draft_by_id(draft_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE id=?", (draft_id,)
        ).fetchone()


def get_draft_by_tweet_id(tweet_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE tweet_id=?", (tweet_id,)
        ).fetchone()


# ── DMs ───────────────────────────────────────────────────────────────────────

def save_dm_draft(dm_id: str, sender_id: str, sender_username: str,
                  original_text: str, draft_text: str,
                  context_analysis: str) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO dm_drafts
                (dm_id, sender_id, sender_username, original_text, draft_text,
                 context_analysis, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (dm_id, sender_id, sender_username, original_text, draft_text,
              context_analysis, now, now))
        conn.commit()
        return cursor.lastrowid


def get_pending_dm_drafts() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM dm_drafts WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()


def update_dm_draft_status(draft_id: int, status: str, new_text: str | None = None):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        if new_text is not None:
            conn.execute(
                "UPDATE dm_drafts SET status=?, draft_text=?, updated_at=? WHERE id=?",
                (status, new_text, now, draft_id)
            )
        else:
            conn.execute(
                "UPDATE dm_drafts SET status=?, updated_at=? WHERE id=?",
                (status, now, draft_id)
            )
        conn.commit()


def mark_dm_processed(dm_id: str):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_dms (dm_id, processed_at) VALUES (?,?)",
            (dm_id, now)
        )
        conn.commit()


def is_dm_processed(dm_id: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM processed_dms WHERE dm_id=?", (dm_id,)
        ).fetchone() is not None


# ── Scheduled Tweets ──────────────────────────────────────────────────────────

def create_scheduled_tweet(text: str, scheduled_at: str,
                            account_name: str = "main") -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO scheduled_tweets (text, scheduled_at, status, account_name, created_at)
            VALUES (?, ?, 'pending', ?, ?)
        """, (text, scheduled_at, account_name, now))
        conn.commit()
        return cursor.lastrowid


def get_scheduled_tweets(account_name: str | None = None) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if account_name:
            return conn.execute(
                "SELECT * FROM scheduled_tweets WHERE account_name=? ORDER BY scheduled_at ASC",
                (account_name,)
            ).fetchall()
        return conn.execute(
            "SELECT * FROM scheduled_tweets ORDER BY scheduled_at ASC"
        ).fetchall()


def get_due_scheduled_tweets(account_name: str = "main") -> list[sqlite3.Row]:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM scheduled_tweets
               WHERE status='pending' AND scheduled_at <= ? AND account_name=?
               ORDER BY scheduled_at ASC""",
            (now, account_name)
        ).fetchall()


def get_scheduled_tweets_count(account_name: str = "main") -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM scheduled_tweets WHERE status='pending' AND account_name=?",
            (account_name,)
        ).fetchone()[0]


def get_next_scheduled_tweet(account_name: str = "main") -> sqlite3.Row | None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM scheduled_tweets
               WHERE status='pending' AND scheduled_at > ? AND account_name=?
               ORDER BY scheduled_at ASC LIMIT 1""",
            (now, account_name)
        ).fetchone()


def update_scheduled_tweet_status(tweet_id: int, status: str,
                                   posted_tweet_id: str | None = None):
    with get_connection() as conn:
        if posted_tweet_id:
            conn.execute(
                "UPDATE scheduled_tweets SET status=?, posted_tweet_id=? WHERE id=?",
                (status, posted_tweet_id, tweet_id)
            )
        else:
            conn.execute(
                "UPDATE scheduled_tweets SET status=? WHERE id=?",
                (status, tweet_id)
            )
        conn.commit()


def cancel_scheduled_tweet(tweet_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE scheduled_tweets SET status='cancelled' WHERE id=? AND status='pending'",
            (tweet_id,)
        )
        conn.commit()


# ── Follower ──────────────────────────────────────────────────────────────────

def save_follower(follower_id: str, username: str, account_name: str = "main"):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO known_followers
               (follower_id, account_name, username, followed_at, welcomed)
               VALUES (?, ?, ?, ?, 0)""",
            (follower_id, account_name, username, now)
        )
        conn.commit()


def is_follower_known(follower_id: str, account_name: str = "main") -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM known_followers WHERE follower_id=? AND account_name=?",
            (follower_id, account_name)
        ).fetchone() is not None


def mark_follower_welcomed(follower_id: str, account_name: str = "main"):
    with get_connection() as conn:
        conn.execute(
            "UPDATE known_followers SET welcomed=1 WHERE follower_id=? AND account_name=?",
            (follower_id, account_name)
        )
        conn.commit()


def get_follower_stats(account_name: str = "main") -> dict:
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM known_followers WHERE account_name=?", (account_name,)
        ).fetchone()[0]
        welcomed = conn.execute(
            "SELECT COUNT(*) FROM known_followers WHERE account_name=? AND welcomed=1",
            (account_name,)
        ).fetchone()[0]
        recent = conn.execute(
            """SELECT username, followed_at FROM known_followers
               WHERE account_name=? ORDER BY followed_at DESC LIMIT 5""",
            (account_name,)
        ).fetchall()
    return {"total": total, "welcomed": welcomed,
            "recent": [dict(r) for r in recent]}


# ── Statistiken ───────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status='approved'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status='rejected'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status='pending'"
        ).fetchone()[0]
        total_dms = conn.execute("SELECT COUNT(*) FROM dm_drafts").fetchone()[0]
        approved_dms = conn.execute(
            "SELECT COUNT(*) FROM dm_drafts WHERE status='approved'"
        ).fetchone()[0]
        scheduled_pending = conn.execute(
            "SELECT COUNT(*) FROM scheduled_tweets WHERE status='pending'"
        ).fetchone()[0]
        total_followers = conn.execute(
            "SELECT COUNT(*) FROM known_followers"
        ).fetchone()[0]

        top_mentioners = conn.execute("""
            SELECT author_username, COUNT(*) as cnt
            FROM drafts GROUP BY author_username
            ORDER BY cnt DESC LIMIT 5
        """).fetchall()

        sentiment_breakdown = conn.execute("""
            SELECT sentiment, COUNT(*) as cnt
            FROM drafts GROUP BY sentiment ORDER BY cnt DESC
        """).fetchall()

        daily_activity = conn.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM drafts WHERE created_at >= DATE('now', '-7 days')
            GROUP BY day ORDER BY day ASC
        """).fetchall()

    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "total_dms": total_dms,
        "approved_dms": approved_dms,
        "scheduled_pending": scheduled_pending,
        "total_followers": total_followers,
        "top_mentioners": [dict(r) for r in top_mentioners],
        "sentiment_breakdown": [dict(r) for r in sentiment_breakdown],
        "daily_activity": [dict(r) for r in daily_activity],
    }
