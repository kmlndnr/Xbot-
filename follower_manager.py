"""
Follower Manager
Erkennt neue Follower und sendet ihnen automatisch eine Willkommens-DM.
"""

import os
from datetime import datetime

import db
import twitter_client as tc
import agent
from dotenv import load_dotenv

load_dotenv()

_WELCOME_TEMPLATE = os.getenv(
    "WELCOME_DM_TEXT",
    "Hey {username}! Danke, dass du mir folgst. "
    "Schau gern mal bei meinen Inhalten vorbei – freue mich auf den Austausch! 👋"
)


def _build_welcome_text(username: str, use_ai: bool = False) -> str:
    if use_ai:
        try:
            result = agent.generate_dm_reply(
                dm_text=f"[Neuer Follower: @{username}]",
                sender_username=username,
            )
            return result["draft_text"]
        except Exception:
            pass
    return _WELCOME_TEMPLATE.replace("{username}", username)


def check_new_followers(account_name: str = "main",
                        welcome_enabled: bool = True,
                        use_ai_welcome: bool = False) -> int:
    """
    Holt aktuelle Follower, erkennt neue und sendet ggf. Willkommens-DMs.
    Gibt die Anzahl neu erkannter Follower zurück.
    """
    try:
        followers = tc.fetch_followers()
    except Exception as exc:
        print(f"  Follower-Fehler: {exc}")
        return 0

    if not followers:
        return 0

    new_count = 0
    for follower in followers:
        fid = follower["follower_id"]
        username = follower["username"]

        if db.is_follower_known(fid, account_name):
            continue

        db.save_follower(fid, username, account_name)
        new_count += 1
        print(f"  Neuer Follower: @{username}")

        if welcome_enabled:
            welcome_text = _build_welcome_text(username, use_ai_welcome)
            try:
                tc.reply_to_dm(fid, welcome_text)
                db.mark_follower_welcomed(fid, account_name)
                print(f"  Willkommens-DM gesendet an @{username}.")
            except Exception as exc:
                print(f"  DM-Fehler an @{username}: {exc}")

    return new_count


def get_follower_stats(account_name: str = "main") -> dict:
    return db.get_follower_stats(account_name)
