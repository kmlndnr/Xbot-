import os
import time
import signal
import sys
from datetime import datetime

import db
import agent
import twitter_client as tc

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))

_since_id: str | None = None
_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n\n  Stoppe Auto-Modus ... (aktueller Durchlauf wird abgeschlossen)")
    _running = False


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _process_mention(mention: dict) -> bool:
    """Generiert eine Antwort und postet sie direkt. Gibt True bei Erfolg zurück."""
    tweet_id = mention["tweet_id"]
    username = mention["author_username"]
    text = mention["text"]

    print(f"  [{_ts()}] @{username}: \"{text[:70]}{'...' if len(text) > 70 else ''}\"")

    try:
        result = agent.generate_draft(tweet_text=text, author_username=username)
    except Exception as exc:
        print(f"  KI-Fehler: {exc}")
        return False

    draft_text = result["draft_text"]

    if len(draft_text) > 280:
        print(f"  Warnung: Entwurf zu lang ({len(draft_text)} Zeichen), wird gekürzt.")
        draft_text = draft_text[:277] + "..."

    try:
        new_tweet_id = tc.post_reply(draft_text, tweet_id)
    except Exception as exc:
        print(f"  Post-Fehler: {exc}")
        db.save_draft(
            tweet_id=tweet_id,
            author_username=username,
            original_text=text,
            draft_text=draft_text,
            context_analysis=result["context_analysis"],
        )
        db.mark_tweet_processed(tweet_id)
        print(f"  Entwurf als 'pending' gespeichert – manuell über Review Queue posten.")
        return False

    db.save_draft(
        tweet_id=tweet_id,
        author_username=username,
        original_text=text,
        draft_text=draft_text,
        context_analysis=result["context_analysis"],
    )
    # Draft auf approved setzen
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE drafts SET status = 'approved' WHERE tweet_id = ?", (tweet_id,)
        )
        conn.commit()

    db.mark_tweet_processed(tweet_id)
    print(f"  Geantwortet (Tweet-ID: {new_tweet_id}): \"{draft_text[:60]}...\"")
    return True


def run_auto_mode():
    global _since_id, _running
    _running = True

    signal.signal(signal.SIGINT, _signal_handler)

    print(f"\n  Auto-Modus gestartet. Polling alle {POLL_INTERVAL}s. Stoppen: Ctrl+C")
    print(f"  {'─' * 56}")

    while _running:
        print(f"\n  [{_ts()}] Prüfe auf neue Mentions ...")

        try:
            mentions = tc.fetch_mentions(since_id=_since_id)
        except Exception as exc:
            print(f"  API-Fehler: {exc}. Nächster Versuch in {POLL_INTERVAL}s.")
            _wait(POLL_INTERVAL)
            continue

        new_mentions = [m for m in mentions if not db.is_tweet_processed(m["tweet_id"])]

        if not new_mentions:
            print(f"  Keine neuen Mentions. Nächster Check in {POLL_INTERVAL}s.")
        else:
            print(f"  {len(new_mentions)} neue Mention(s) gefunden:")
            replied = 0
            for mention in new_mentions:
                if not _running:
                    break
                success = _process_mention(mention)
                if success:
                    replied += 1
                # Kurze Pause zwischen Posts um Rate-Limits zu schonen
                if len(new_mentions) > 1:
                    time.sleep(2)

            # Since-ID auf neuesten Tweet aktualisieren
            if mentions:
                latest_id = max(int(m["tweet_id"]) for m in mentions)
                _since_id = str(latest_id)

            print(f"  {replied}/{len(new_mentions)} Antworten gepostet.")

        if _running:
            _wait(POLL_INTERVAL)

    print(f"\n  [{_ts()}] Auto-Modus beendet.")


def _wait(seconds: int):
    """Wartet N Sekunden, bricht aber sofort ab wenn _running False wird."""
    global _running
    for _ in range(seconds):
        if not _running:
            break
        time.sleep(1)
