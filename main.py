import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

import db
import agent
import twitter_client as tc
from cli import review_queue, manage_scheduler, SEPARATOR
from auto_reply import run_auto_mode
from stats import print_stats


_since_id_cache: str | None = None


def fetch_and_generate():
    global _since_id_cache

    print("\n  Rufe neue Mentions ab ...")
    try:
        mentions = tc.fetch_mentions(since_id=_since_id_cache)
    except Exception as exc:
        print(f"  Fehler: {exc}")
        return

    if not mentions:
        print("  Keine neuen Mentions.")
        return

    print(f"  {len(mentions)} Mention(s) gefunden.")
    new_drafts = 0

    for mention in mentions:
        tweet_id = mention["tweet_id"]
        if db.is_tweet_processed(tweet_id):
            continue

        print(f"\n  @{mention['author_username']}: \"{mention['text'][:80]}\"")

        thread_context = None
        if mention.get("conversation_id"):
            thread_context = tc.fetch_thread_context(
                mention["conversation_id"], exclude_tweet_id=tweet_id
            ) or None

        try:
            result = agent.generate_draft(
                tweet_text=mention["text"],
                author_username=mention["author_username"],
                thread_context=thread_context,
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

    print(f"\n  {new_drafts} neuer/neue Entwurf/Entwürfe erstellt.")
    if new_drafts > 0:
        print("  Wechsle zu 'Review Queue' [2] oder 'Web-Dashboard' [5].")


def run_web():
    print("\n  Starte Web-Dashboard ...")
    print("  URL: http://localhost:5000  |  Stoppen: Ctrl+C\n")
    from web_dashboard.app import run
    run()


def run_multi_account():
    from accounts import run_all_accounts
    run_all_accounts()


def run_scheduler_standalone():
    from scheduler import run_scheduler_loop
    run_scheduler_loop()


def show_main_menu() -> str:
    print(f"\n{SEPARATOR}")
    print("  XBOT – Twitter Agent")
    print(SEPARATOR)
    print("  [1]  Fetch & Generate      –  Mentions holen & Entwürfe erstellen")
    print("  [2]  Review Queue          –  Entwürfe manuell prüfen")
    print("  [3]  Auto-Modus            –  Automatisch antworten (1 Account)")
    print("  [4]  Multi-Account Modus   –  Alle Accounts parallel betreiben")
    print("  [5]  Web-Dashboard         –  Browser-Interface starten")
    print("  [6]  Tweet-Planer          –  Tweets zeitgesteuert planen")
    print("  [7]  Tweet-Scheduler       –  Scheduler-Daemon starten")
    print("  [8]  Statistiken           –  Übersicht anzeigen")
    print("  [q]  Beenden")
    print()
    return input("  Deine Wahl: ").strip().lower()


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--multi", action="store_true")
    parser.add_argument("--scheduler", action="store_true")
    args, _ = parser.parse_known_args()

    db.init_db()

    if args.auto:
        run_auto_mode()
        return
    if args.web:
        run_web()
        return
    if args.multi:
        run_multi_account()
        return
    if args.scheduler:
        run_scheduler_standalone()
        return

    print(f"\n{SEPARATOR}")
    print("  Willkommen bei Xbot")
    print(f"{SEPARATOR}")

    while True:
        choice = show_main_menu()

        if choice == "1":
            fetch_and_generate()
        elif choice == "2":
            review_queue()
        elif choice == "3":
            run_auto_mode()
        elif choice == "4":
            run_multi_account()
        elif choice == "5":
            run_web()
        elif choice == "6":
            manage_scheduler()
        elif choice == "7":
            run_scheduler_standalone()
        elif choice == "8":
            print_stats()
        elif choice in ("q", "quit", "exit"):
            print("\n  Tschüss!\n")
            sys.exit(0)
        else:
            print("  Unbekannte Eingabe.")


if __name__ == "__main__":
    main()
