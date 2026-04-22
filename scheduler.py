"""
Tweet-Scheduler
Postet geplante Tweets zum vorgesehenen Zeitpunkt.

Standalone starten: python scheduler.py
Oder über main.py Menü-Option [6].
"""

import time
import signal
import sys
from datetime import datetime

import db
import twitter_client as tc

_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n\n  Stoppe Scheduler ...")
    _running = False


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def check_and_post_due_tweets(account_name: str = "main") -> int:
    """
    Prüft auf fällige Tweets und postet sie.
    Gibt die Anzahl der geposteten Tweets zurück.
    """
    due = db.get_due_scheduled_tweets(account_name)
    if not due:
        return 0

    posted = 0
    for tweet in due:
        print(f"  [{_ts()}] Geplanter Tweet fällig (ID {tweet['id']}): "
              f"\"{tweet['text'][:60]}...\"")
        try:
            client = tc._get_client()
            response = client.create_tweet(text=tweet["text"])
            if response.data:
                new_id = str(response.data["id"])
                db.update_scheduled_tweet_status(tweet["id"], "posted", new_id)
                print(f"  Gepostet! Tweet-ID: {new_id}")
                posted += 1
            else:
                print(f"  Fehler: Keine Antwort von der API.")
        except Exception as exc:
            print(f"  Fehler beim Posten: {exc}")
            db.update_scheduled_tweet_status(tweet["id"], "failed")

    return posted


def run_scheduler_loop(check_interval: int = 60):
    """Dauerhafter Loop, der minütlich auf fällige Tweets prüft."""
    global _running
    _running = True
    signal.signal(signal.SIGINT, _signal_handler)

    print(f"\n  Tweet-Scheduler gestartet. Check alle {check_interval}s | Ctrl+C zum Stoppen")
    print(f"  {'─' * 56}")

    while _running:
        now_str = datetime.now().strftime("%H:%M:%S")
        pending = db.get_scheduled_tweets_count()
        print(f"\n  [{now_str}] Prüfe geplante Tweets ({pending} ausstehend) ...")

        posted = check_and_post_due_tweets()
        if posted == 0 and pending > 0:
            next_tweet = db.get_next_scheduled_tweet()
            if next_tweet:
                print(f"  Nächster Tweet geplant für: {next_tweet['scheduled_at'][:16]}")

        _wait(check_interval)

    print(f"\n  Scheduler beendet.")


def _wait(seconds: int):
    global _running
    for _ in range(seconds):
        if not _running:
            break
        time.sleep(1)


if __name__ == "__main__":
    db.init_db()
    run_scheduler_loop()
