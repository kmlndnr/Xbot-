import sys
import textwrap

from db import (
    get_pending_drafts,
    get_pending_dm_drafts,
    update_draft_status,
    update_dm_draft_status,
    get_draft_by_id,
)
from twitter_client import post_reply, reply_to_dm


SEPARATOR = "─" * 60


def _wrap(text: str, width: int = 58, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def review_queue():
    drafts = list(get_pending_drafts())
    dm_drafts = list(get_pending_dm_drafts())

    if not drafts and not dm_drafts:
        print("\n  Keine ausstehenden Entwürfe. Führe zuerst 'Fetch & Generate' aus.")
        return

    if drafts:
        print(f"\n  {len(drafts)} Tweet-Entwurf/Entwürfe in der Queue.")
        for draft in drafts:
            _review_tweet_draft(draft)

    if dm_drafts:
        print(f"\n  {len(dm_drafts)} DM-Entwurf/Entwürfe in der Queue.")
        for draft in dm_drafts:
            _review_dm_draft(draft)

    print(f"\n{SEPARATOR}")
    print("  Queue abgearbeitet.")


def _review_tweet_draft(draft):
    print(f"\n{SEPARATOR}")
    print(f"  Tweet-Entwurf #{draft['id']} – @{draft['author_username']}")
    print(SEPARATOR)

    print("\n  ORIGINAL TWEET:")
    print(_wrap(draft["original_text"]))

    if draft["context_analysis"]:
        print("\n  KONTEXT-ANALYSE:")
        print(_wrap(draft["context_analysis"]))

    print("\n  ENTWURFS-TEXT:")
    print(_wrap(draft["draft_text"]))
    char_count = len(draft["draft_text"])
    color = "\033[92m" if char_count <= 280 else "\033[91m"
    print(f"\n  {color}Zeichen: {char_count}/280\033[0m")

    print()
    print("  [y] Freigeben & posten  [n] Ablehnen  [e] Bearbeiten  [s] Überspringen")
    action = input("  Aktion: ").strip().lower()

    if action == "y":
        _approve_tweet(draft)
    elif action == "n":
        update_draft_status(draft["id"], "rejected")
        print("  Entwurf abgelehnt.")
    elif action == "e":
        _edit_tweet_draft(draft)
    elif action == "s":
        print("  Übersprungen.")
    else:
        print("  Unbekannte Eingabe – übersprungen.")


def _approve_tweet(draft):
    try:
        tweet_id = post_reply(draft["draft_text"], draft["tweet_id"])
        update_draft_status(draft["id"], "approved")
        print(f"  Gepostet! Tweet-ID: {tweet_id}")
    except Exception as exc:
        print(f"  Fehler beim Posten: {exc}")
        print("  Status bleibt 'pending'.")


def _edit_tweet_draft(draft):
    print("\n  Aktueller Text:")
    print(f"\n  {draft['draft_text']}\n")
    print("  Neuen Text eingeben (leere Eingabe = Abbrechen):")
    new_text = input("  > ").strip()

    if not new_text:
        print("  Abgebrochen.")
        return

    char_count = len(new_text)
    if char_count > 280:
        print(f"  Warnung: {char_count} Zeichen (Limit: 280)")

    print(f"\n  Neuer Text ({char_count}/280):")
    print(_wrap(new_text))
    confirm = input("\n  Freigeben & posten? [y/n]: ").strip().lower()

    if confirm == "y":
        update_draft_status(draft["id"], "pending", new_text=new_text)
        updated = get_draft_by_id(draft["id"])
        _approve_tweet(updated)
    else:
        update_draft_status(draft["id"], "pending", new_text=new_text)
        print("  Text gespeichert, aber noch nicht gepostet.")


def _review_dm_draft(draft):
    print(f"\n{SEPARATOR}")
    print(f"  DM-Entwurf #{draft['id']} – @{draft['sender_username']}")
    print(SEPARATOR)

    print("\n  ORIGINAL DM:")
    print(_wrap(draft["original_text"]))

    if draft["context_analysis"]:
        print("\n  KONTEXT-ANALYSE:")
        print(_wrap(draft["context_analysis"]))

    print("\n  ENTWURFS-ANTWORT:")
    print(_wrap(draft["draft_text"]))

    print()
    print("  [y] Senden  [n] Ablehnen  [s] Überspringen")
    action = input("  Aktion: ").strip().lower()

    if action == "y":
        try:
            reply_to_dm(draft["sender_id"], draft["draft_text"])
            update_dm_draft_status(draft["id"], "approved")
            print("  DM gesendet.")
        except Exception as exc:
            print(f"  Fehler: {exc}")
    elif action == "n":
        update_dm_draft_status(draft["id"], "rejected")
        print("  Abgelehnt.")
    else:
        print("  Übersprungen.")
