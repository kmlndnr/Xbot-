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
        conn.commit()


def save_draft(tweet_id: str, author_username: str, original_text: str,
               draft_text: str, context_analysis: str) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO drafts
                (tweet_id, author_username, original_text, draft_text, context_analysis, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (tweet_id, author_username, original_text, draft_text, context_analysis, now, now))
        conn.commit()
        return cursor.lastrowid


def get_pending_drafts() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE status = 'pending' ORDER BY created_at ASC"
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
