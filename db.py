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
        conn.commit()


# ── Mentions / Drafts ──────────────────────────────────────────────────────────

def save_draft(tweet_id: str, author_username: str, original_text: str,
               draft_text: str, context_analysis: str,
               source: str = "mention") -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO drafts
                (tweet_id, author_username, original_text, draft_text,
                 context_analysis, status, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (tweet_id, author_username, original_text, draft_text,
              context_analysis, source, now, now))
        conn.commit()
        return cursor.lastrowid


def get_pending_drafts() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE status = 'pending' ORDER BY created_at ASC"
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
                "UPDATE drafts SET status = ?, draft_text = ?, updated_at = ? WHERE id = ?",
                (status, new_text, now, draft_id)
            )
        else:
            conn.execute(
                "UPDATE drafts SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, draft_id)
            )
        conn.commit()


def mark_tweet_processed(tweet_id: str):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_tweets (tweet_id, processed_at) VALUES (?, ?)",
            (tweet_id, now)
        )
        conn.commit()


def is_tweet_processed(tweet_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_tweets WHERE tweet_id = ?", (tweet_id,)
        ).fetchone()
        return row is not None


def get_draft_by_id(draft_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE id = ?", (draft_id,)
        ).fetchone()


def get_draft_by_tweet_id(tweet_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE tweet_id = ?", (tweet_id,)
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
            "SELECT * FROM dm_drafts WHERE status = 'pending' ORDER BY created_at ASC"
        ).fetchall()


def update_dm_draft_status(draft_id: int, status: str, new_text: str | None = None):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        if new_text is not None:
            conn.execute(
                "UPDATE dm_drafts SET status = ?, draft_text = ?, updated_at = ? WHERE id = ?",
                (status, new_text, now, draft_id)
            )
        else:
            conn.execute(
                "UPDATE dm_drafts SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, draft_id)
            )
        conn.commit()


def mark_dm_processed(dm_id: str):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_dms (dm_id, processed_at) VALUES (?, ?)",
            (dm_id, now)
        )
        conn.commit()


def is_dm_processed(dm_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_dms WHERE dm_id = ?", (dm_id,)
        ).fetchone()
        return row is not None


# ── Statistiken ───────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status = 'approved'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status = 'rejected'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status = 'pending'"
        ).fetchone()[0]
        total_dms = conn.execute("SELECT COUNT(*) FROM dm_drafts").fetchone()[0]
        approved_dms = conn.execute(
            "SELECT COUNT(*) FROM dm_drafts WHERE status = 'approved'"
        ).fetchone()[0]

        top_mentioners = conn.execute("""
            SELECT author_username, COUNT(*) as cnt
            FROM drafts
            GROUP BY author_username
            ORDER BY cnt DESC
            LIMIT 5
        """).fetchall()

        daily_activity = conn.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM drafts
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY day
            ORDER BY day ASC
        """).fetchall()

    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "total_dms": total_dms,
        "approved_dms": approved_dms,
        "top_mentioners": [dict(r) for r in top_mentioners],
        "daily_activity": [dict(r) for r in daily_activity],
    }
