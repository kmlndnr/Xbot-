"""
Multi-Account Manager
Lädt accounts.json und startet für jeden Account einen eigenen Thread.

Starten: python accounts.py
Oder über main.py Menü-Option [7].
"""

import os
import json
import threading
import signal
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ACCOUNTS_FILE = "accounts.json"

_threads: list[threading.Thread] = []
_stop_event = threading.Event()


def load_accounts() -> list[dict]:
    if not os.path.exists(ACCOUNTS_FILE):
        raise FileNotFoundError(
            f"{ACCOUNTS_FILE} nicht gefunden. "
            f"Erstelle sie aus accounts.json.example:\n"
            f"  cp accounts.json.example accounts.json"
        )
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        accounts = json.load(f)
    if not accounts:
        raise ValueError("accounts.json ist leer.")
    return accounts


def _run_account_loop(account: dict):
    """Läuft in einem eigenen Thread für einen Account."""
    name = account["name"]
    print(f"  [Account: {name}] Gestartet.")

    # Temporär Umgebungsvariablen für diesen Thread setzen
    # (wird durch os.environ nicht thread-sicher, daher übergeben wir creds direkt)
    creds = {
        "bearer_token": account.get("twitter_bearer_token") or os.getenv("TWITTER_BEARER_TOKEN"),
        "api_key": account.get("twitter_api_key") or os.getenv("TWITTER_API_KEY"),
        "api_secret": account.get("twitter_api_secret") or os.getenv("TWITTER_API_SECRET"),
        "access_token": account.get("twitter_access_token") or os.getenv("TWITTER_ACCESS_TOKEN"),
        "access_secret": account.get("twitter_access_secret") or os.getenv("TWITTER_ACCESS_SECRET"),
        "user_id": account.get("twitter_user_id", ""),
        "anthropic_api_key": account.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY"),
    }

    import db
    import twitter_client as tc
    import agent as ag
    import sentiment as sent
    import follower_manager as fm
    from scheduler import check_and_post_due_tweets

    poll_interval = account.get("poll_interval_seconds", 900)
    keyword_filter = [k.lower() for k in account.get("keyword_filter", [])]
    blacklist = [u.lower().lstrip("@") for u in account.get("blacklist_accounts", [])]
    quiet_start = account.get("quiet_hours_start", 23)
    quiet_end = account.get("quiet_hours_end", 7)
    dms_enabled = account.get("dms_enabled", False)
    auto_like = account.get("auto_like_mentions", False)
    auto_rt = account.get("auto_retweet_mentions", False)
    sentiment_block = account.get("sentiment_block", ["aggressive"])
    welcome_followers = account.get("welcome_new_followers", False)
    welcome_text = account.get("welcome_dm_text", "Hey {username}! Danke fürs Folgen 👋")

    since_id = None

    while not _stop_event.is_set():
        hour = datetime.now().hour
        is_quiet = (quiet_start > quiet_end and (hour >= quiet_start or hour < quiet_end)) or \
                   (quiet_start <= quiet_end and quiet_start <= hour < quiet_end)

        if not is_quiet:
            # Geplante Tweets prüfen
            check_and_post_due_tweets(account_name=name)

            # Neue Follower
            if welcome_followers:
                os.environ["WELCOME_DM_TEXT"] = welcome_text
                fm.check_new_followers(account_name=name, welcome_enabled=True)

            # Mentions
            try:
                mentions = tc.fetch_mentions_with_creds(creds, since_id=since_id)
            except Exception as exc:
                print(f"  [Account: {name}] API-Fehler: {exc}")
                mentions = []

            new_mentions = [m for m in mentions if not db.is_tweet_processed(m["tweet_id"])]

            for mention in new_mentions:
                if _stop_event.is_set():
                    break

                username = mention["author_username"].lower()
                text = mention["text"]

                if username in blacklist:
                    db.mark_tweet_processed(mention["tweet_id"])
                    continue

                if keyword_filter and not any(k in text.lower() for k in keyword_filter):
                    db.mark_tweet_processed(mention["tweet_id"])
                    continue

                # Sentiment-Filter
                if sentiment_block:
                    skip, detected = sent.should_skip(text, sentiment_block)
                    if skip:
                        print(f"  [Account: {name}] Übersprungen (Sentiment: {detected}): @{username}")
                        db.mark_tweet_processed(mention["tweet_id"])
                        continue

                # Auto-Like
                if auto_like:
                    try:
                        tc.like_tweet_with_creds(creds, mention["tweet_id"])
                    except Exception:
                        pass

                # Auto-Retweet
                if auto_rt:
                    try:
                        tc.retweet_with_creds(creds, mention["tweet_id"])
                    except Exception:
                        pass

                # KI-Antwort generieren
                try:
                    result = ag.generate_draft(
                        tweet_text=text,
                        author_username=mention["author_username"],
                    )
                    draft_text = result["draft_text"]
                    if len(draft_text) > 280:
                        draft_text = draft_text[:277] + "..."

                    tc.post_reply_with_creds(creds, draft_text, mention["tweet_id"])
                    db.save_draft(
                        tweet_id=mention["tweet_id"],
                        author_username=mention["author_username"],
                        original_text=text,
                        draft_text=draft_text,
                        context_analysis=result["context_analysis"],
                        account_name=name,
                    )
                    with db.get_connection() as conn:
                        conn.execute(
                            "UPDATE drafts SET status='approved' WHERE tweet_id=?",
                            (mention["tweet_id"],)
                        )
                        conn.commit()
                    print(f"  [Account: {name}] Geantwortet auf @{mention['author_username']}")
                except Exception as exc:
                    print(f"  [Account: {name}] Fehler: {exc}")

                db.mark_tweet_processed(mention["tweet_id"])
                time.sleep(2)

            if mentions:
                since_id = str(max(int(m["tweet_id"]) for m in mentions))

        # Warten mit Stop-Event-Check
        for _ in range(poll_interval):
            if _stop_event.is_set():
                break
            time.sleep(1)

    print(f"  [Account: {name}] Beendet.")


def run_all_accounts():
    global _threads
    _stop_event.clear()

    try:
        accounts = load_accounts()
    except (FileNotFoundError, ValueError) as exc:
        print(f"\n  Fehler: {exc}")
        return

    print(f"\n  Multi-Account Modus: {len(accounts)} Account(s) geladen.")
    for acc in accounts:
        print(f"    - {acc['name']}")

    def _signal_handler(sig, frame):
        print("\n\n  Stoppe alle Accounts ...")
        _stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)

    _threads = []
    for account in accounts:
        t = threading.Thread(
            target=_run_account_loop,
            args=(account,),
            name=f"xbot-{account['name']}",
            daemon=True,
        )
        t.start()
        _threads.append(t)

    print(f"\n  Alle Threads gestartet. Ctrl+C zum Stoppen.\n")

    # Warten bis alle Threads beendet sind
    while not _stop_event.is_set():
        time.sleep(1)

    for t in _threads:
        t.join(timeout=10)

    print("\n  Alle Accounts gestoppt.")


if __name__ == "__main__":
    import db as _db
    _db.init_db()
    run_all_accounts()
