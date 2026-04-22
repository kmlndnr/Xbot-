import textwrap
from datetime import datetime

from db import (
    get_pending_drafts, get_pending_dm_drafts,
    update_draft_status, update_dm_draft_status, get_draft_by_id,
    get_scheduled_tweets, create_scheduled_tweet, cancel_scheduled_tweet,
)
from twitter_client import post_reply, reply_to_dm

SEPARATOR = "─" * 60


def _wrap(text: str, width: int = 58, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent,
                         subsequent_indent=indent)


# ── Review Queue ───────────────────────────────────────────────────────────────

def review_queue():
    drafts = list(get_pending_drafts())
    dm_drafts = list(get_pending_dm_drafts())

    if not drafts and not dm_drafts:
        print("\n  Keine ausstehenden Entwürfe.")
        return

    if drafts:
        print(f"\n  {len(drafts)} Tweet-Entwurf/Entwürfe:")
        for draft in drafts:
            _review_tweet_draft(draft)

    if dm_drafts:
        print(f"\n  {len(dm_drafts)} DM-Entwurf/Entwürfe:")
        for draft in dm_drafts:
            _review_dm_draft(draft)

    print(f"\n{SEPARATOR}\n  Queue abgearbeitet.")


def _review_tweet_draft(draft):
    print(f"\n{SEPARATOR}")
    print(f"  Tweet #{draft['id']} – @{draft['author_username']}", end="")
    if draft["sentiment"]:
        print(f"  [{draft['sentiment']}]", end="")
    print()
    print(SEPARATOR)
    print("\n  ORIGINAL:")
    print(_wrap(draft["original_text"]))
    if draft["context_analysis"]:
        print("\n  ANALYSE:")
        print(_wrap(draft["context_analysis"]))
    print("\n  ENTWURF:")
    print(_wrap(draft["draft_text"]))
    char_count = len(draft["draft_text"])
    color = "\033[92m" if char_count <= 280 else "\033[91m"
    print(f"\n  {color}{char_count}/280 Zeichen\033[0m")
    print("\n  [y] Posten  [n] Ablehnen  [e] Bearbeiten  [s] Überspringen")
    action = input("  > ").strip().lower()

    if action == "y":
        _approve_tweet(draft)
    elif action == "n":
        update_draft_status(draft["id"], "rejected")
        print("  Abgelehnt.")
    elif action == "e":
        _edit_tweet_draft(draft)
    else:
        print("  Übersprungen.")


def _approve_tweet(draft):
    try:
        tweet_id = post_reply(draft["draft_text"], draft["tweet_id"])
        update_draft_status(draft["id"], "approved")
        print(f"  ✅ Gepostet! Tweet-ID: {tweet_id}")
    except Exception as exc:
        print(f"  Fehler: {exc}")


def _edit_tweet_draft(draft):
    print(f"\n  Aktuell: {draft['draft_text']}\n")
    new_text = input("  Neuer Text (leer = Abbrechen): ").strip()
    if not new_text:
        print("  Abgebrochen.")
        return
    char_count = len(new_text)
    if char_count > 280:
        print(f"  ⚠️  {char_count} Zeichen (Limit: 280)")
    confirm = input(f"  Posten? ({char_count}/280) [y/n]: ").strip().lower()
    if confirm == "y":
        update_draft_status(draft["id"], "pending", new_text=new_text)
        _approve_tweet(get_draft_by_id(draft["id"]))
    else:
        update_draft_status(draft["id"], "pending", new_text=new_text)
        print("  Gespeichert, aber nicht gepostet.")


def _review_dm_draft(draft):
    print(f"\n{SEPARATOR}")
    print(f"  DM #{draft['id']} – @{draft['sender_username']}")
    print(SEPARATOR)
    print("\n  ORIGINAL:")
    print(_wrap(draft["original_text"]))
    print("\n  ANTWORT-ENTWURF:")
    print(_wrap(draft["draft_text"]))
    print("\n  [y] Senden  [n] Ablehnen  [s] Überspringen")
    action = input("  > ").strip().lower()
    if action == "y":
        try:
            reply_to_dm(draft["sender_id"], draft["draft_text"])
            update_dm_draft_status(draft["id"], "approved")
            print("  ✅ DM gesendet.")
        except Exception as exc:
            print(f"  Fehler: {exc}")
    elif action == "n":
        update_dm_draft_status(draft["id"], "rejected")
        print("  Abgelehnt.")
    else:
        print("  Übersprungen.")


# ── Scheduler Management ───────────────────────────────────────────────────────

def manage_scheduler():
    while True:
        print(f"\n{SEPARATOR}")
        print("  TWEET-PLANER")
        print(SEPARATOR)

        tweets = get_scheduled_tweets()
        pending = [t for t in tweets if t["status"] == "pending"]
        posted = [t for t in tweets if t["status"] == "posted"]

        print(f"\n  Geplant: {len(pending)} | Gepostet: {len(posted)}")

        if pending:
            print("\n  Ausstehende Tweets:")
            for tw in pending:
                print(f"    [{tw['id']}] {tw['scheduled_at'][:16]}  "
                      f"\"{tw['text'][:50]}{'...' if len(tw['text'])>50 else ''}\"")

        print()
        print("  [n] Neuen Tweet planen")
        print("  [c] Tweet stornieren")
        print("  [b] Zurück")
        choice = input("  > ").strip().lower()

        if choice == "n":
            _create_scheduled_tweet()
        elif choice == "c":
            _cancel_scheduled_tweet(pending)
        elif choice == "b":
            break
        else:
            print("  Unbekannte Eingabe.")


def _create_scheduled_tweet():
    print("\n  Tweet-Text eingeben (max. 280 Zeichen):")
    text = input("  > ").strip()
    if not text:
        print("  Abgebrochen.")
        return
    if len(text) > 280:
        print(f"  ⚠️  Text zu lang ({len(text)} Zeichen).")
        return

    print("\n  Zeitpunkt (Format: YYYY-MM-DD HH:MM):")
    time_str = input("  > ").strip()
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        scheduled_at = dt.isoformat()
    except ValueError:
        print("  Ungültiges Format. Beispiel: 2025-12-31 14:30")
        return

    tweet_id = create_scheduled_tweet(text, scheduled_at)
    print(f"\n  ✅ Tweet #{tweet_id} geplant für {scheduled_at[:16]}.")


def _cancel_scheduled_tweet(pending: list):
    if not pending:
        print("  Keine ausstehenden Tweets.")
        return
    id_str = input("  ID zum Stornieren eingeben: ").strip()
    try:
        cancel_scheduled_tweet(int(id_str))
        print(f"  Tweet #{id_str} storniert.")
    except ValueError:
        print("  Ungültige ID.")
