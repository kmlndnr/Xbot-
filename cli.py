import sys
import textwrap

from db import (
    get_pending_drafts,
    update_draft_status,
    get_draft_by_id,
)
from twitter_client import post_reply


SEPARATOR = "─" * 60


def _print_header(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def _wrap(text: str, width: int = 58, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def show_main_menu() -> str:
    _print_header("XBOT – Human-in-the-Loop Twitter Agent")
    print("  [1]  Fetch & Generate  –  Neue Mentions holen & Entwürfe erstellen")
    print("  [2]  Review Queue      –  Entwürfe prüfen, freigeben oder ablehnen")
    print("  [q]  Beenden")
    print()
    choice = input("  Deine Wahl: ").strip().lower()
    return choice


def review_queue():
    drafts = get_pending_drafts()

    if not drafts:
        print("\n  Keine ausstehenden Entwürfe. Führe zuerst 'Fetch & Generate' aus.")
        return

    print(f"\n  {len(drafts)} Entwurf/Entwürfe in der Queue.")

    for draft in drafts:
        _print_header(f"Entwurf #{draft['id']} – @{draft['author_username']}")

        print("\n  ORIGINAL TWEET:")
        print(_wrap(draft["original_text"]))

        print("\n  KONTEXT-ANALYSE:")
        print(_wrap(draft["context_analysis"] or "–"))

        print("\n  ENTWURFS-TEXT:")
        print(_wrap(draft["draft_text"]))
        char_count = len(draft["draft_text"])
        color = "\033[92m" if char_count <= 280 else "\033[91m"
        print(f"\n  {color}Zeichen: {char_count}/280\033[0m")

        print()
        print("  [y] Freigeben & posten  [n] Ablehnen  [e] Bearbeiten  [s] Überspringen")
        action = input("  Aktion: ").strip().lower()

        if action == "y":
            _approve_draft(draft)
        elif action == "n":
            update_draft_status(draft["id"], "rejected")
            print("  Entwurf abgelehnt.")
        elif action == "e":
            _edit_draft(draft)
        elif action == "s":
            print("  Übersprungen.")
        else:
            print("  Unbekannte Eingabe – übersprungen.")

    print(f"\n{SEPARATOR}")
    print("  Queue abgearbeitet.")


def _approve_draft(draft):
    try:
        tweet_id = post_reply(draft["draft_text"], draft["tweet_id"])
        update_draft_status(draft["id"], "approved")
        print(f"  Gepostet! Neue Tweet-ID: {tweet_id}")
    except Exception as exc:
        print(f"  Fehler beim Posten: {exc}")
        print("  Status bleibt 'pending'.")


def _edit_draft(draft):
    print("\n  Aktueller Text (zum Bearbeiten kopieren):")
    print(f"\n  {draft['draft_text']}\n")
    print("  Gib den neuen Text ein (leere Eingabe = Abbrechen):")
    new_text = input("  > ").strip()

    if not new_text:
        print("  Abgebrochen – keine Änderung.")
        return

    char_count = len(new_text)
    if char_count > 280:
        print(f"  Warnung: Text ist {char_count} Zeichen lang (Limit: 280).")

    print(f"\n  Neuer Text ({char_count}/280 Zeichen):")
    print(_wrap(new_text))
    confirm = input("\n  Freigeben & posten? [y/n]: ").strip().lower()

    if confirm == "y":
        update_draft_status(draft["id"], "pending", new_text=new_text)
        updated = get_draft_by_id(draft["id"])
        _approve_draft(updated)
    else:
        update_draft_status(draft["id"], "pending", new_text=new_text)
        print("  Text gespeichert, aber noch nicht gepostet.")
