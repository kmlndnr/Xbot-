import sys
from dotenv import load_dotenv

load_dotenv()

import db
import agent
import twitter_client as tc
from cli import review_queue, SEPARATOR
from auto_reply import run_auto_mode

_since_id_cache: str | None = None


def fetch_and_generate():
    global _since_id_cache

    print("\n  Rufe neue Mentions ab ...")
    try:
        mentions = tc.fetch_mentions(since_id=_since_id_cache)
    except Exception as exc:
        print(f"  Fehler beim Abrufen der Mentions: {exc}")
        return

    if not mentions:
        print("  Keine neuen Mentions gefunden.")
        return

    print(f"  {len(mentions)} neue Mention(s) gefunden.")
    new_drafts = 0
    skipped = 0

    for mention in mentions:
        tweet_id = mention["tweet_id"]

        if db.is_tweet_processed(tweet_id):
            skipped += 1
            continue

        print(f"\n  Verarbeite Tweet {tweet_id} von @{mention['author_username']} ...")
        print(f"  \"{mention['text'][:80]}{'...' if len(mention['text']) > 80 else ''}\"")

        try:
            result = agent.generate_draft(
                tweet_text=mention["text"],
                author_username=mention["author_username"],
            )
        except Exception as exc:
            print(f"  KI-Fehler: {exc}")
            continue

        db.save_draft(
            tweet_id=tweet_id,
            author_username=mention["author_username"],
            original_text=mention["text"],
            draft_text=result["draft_text"],
            context_analysis=result["context_analysis"],
        )
        db.mark_tweet_processed(tweet_id)
        new_drafts += 1

        if _since_id_cache is None or int(tweet_id) > int(_since_id_cache):
            _since_id_cache = tweet_id

    print(f"\n  Fertig: {new_drafts} neue Entwurf/Entwürfe erstellt, {skipped} bereits bekannt.")
    if new_drafts > 0:
        print("  Wechsle zu 'Review Queue', um die Entwürfe zu prüfen.")


def show_main_menu() -> str:
    print(f"\n{SEPARATOR}")
    print("  XBOT – Twitter Agent")
    print(SEPARATOR)
    print("  [1]  Fetch & Generate  –  Mentions holen & Entwürfe erstellen")
    print("  [2]  Review Queue      –  Entwürfe manuell prüfen & freigeben")
    print("  [3]  Auto-Modus        –  Automatisch antworten (läuft dauerhaft)")
    print("  [q]  Beenden")
    print()
    return input("  Deine Wahl: ").strip().lower()


def main():
    db.init_db()
    print(f"\n{SEPARATOR}")
    print("  Willkommen bei Xbot – dein Twitter Agent")
    print(f"{SEPARATOR}")

    while True:
        choice = show_main_menu()

        if choice == "1":
            fetch_and_generate()
        elif choice == "2":
            review_queue()
        elif choice == "3":
            run_auto_mode()
        elif choice in ("q", "quit", "exit"):
            print("\n  Tschüss!\n")
            sys.exit(0)
        else:
            print("  Unbekannte Eingabe.")


if __name__ == "__main__":
    main()
