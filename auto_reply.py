import os
import time
import signal
from datetime import datetime

import config
import db
import agent
import twitter_client as tc

_since_id: str | None = None
_since_dm_id: str | None = None
_running = True
_tone_cache: list[str] = []
_tone_fetched_at: float = 0
TONE_CACHE_TTL = 3600  # Tone-Profil stündlich neu laden


def _signal_handler(sig, frame):
    global _running
    print("\n\n  Stoppe Auto-Modus ... (aktueller Durchlauf wird abgeschlossen)")
    _running = False


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _is_quiet_hours() -> bool:
    hour = datetime.now().hour
    s, e = config.QUIET_HOURS_START, config.QUIET_HOURS_END
    if s > e:  # z.B. 23-7 (über Mitternacht)
        return hour >= s or hour < e
    return s <= hour < e


def _passes_keyword_filter(text: str) -> bool:
    if not config.KEYWORD_FILTER:
        return True
    text_lower = text.lower()
    return any(kw in text_lower for kw in config.KEYWORD_FILTER)


def _is_blacklisted(username: str) -> bool:
    return username.lower().lstrip("@") in config.BLACKLIST


def _get_tone_examples() -> list[str]:
    global _tone_cache, _tone_fetched_at
    if config.TONE_TWEET_COUNT == 0:
        return []
    now = time.time()
    if now - _tone_fetched_at > TONE_CACHE_TTL:
        try:
            _tone_cache = tc.fetch_user_timeline(count=config.TONE_TWEET_COUNT)
            _tone_fetched_at = now
            print(f"  [{_ts()}] Tone-of-Voice Profil geladen ({len(_tone_cache)} Tweets).")
        except Exception as exc:
            print(f"  Tone-Profil Fehler: {exc}")
    return _tone_cache


def _process_mention(mention: dict) -> bool:
    tweet_id = mention["tweet_id"]
    username = mention["author_username"]
    text = mention["text"]

    if _is_blacklisted(username):
        print(f"  [{_ts()}] Übersprungen (Blacklist): @{username}")
        db.mark_tweet_processed(tweet_id)
        return False

    if not _passes_keyword_filter(text):
        print(f"  [{_ts()}] Übersprungen (Kein Keyword-Match): @{username}")
        db.mark_tweet_processed(tweet_id)
        return False

    print(f"  [{_ts()}] @{username}: \"{text[:70]}{'...' if len(text) > 70 else ''}\"")

    # Thread-Kontext laden
    thread_context = []
    if mention.get("conversation_id"):
        thread_context = tc.fetch_thread_context(
            mention["conversation_id"], exclude_tweet_id=tweet_id
        )

    tone_examples = _get_tone_examples()

    try:
        result = agent.generate_draft(
            tweet_text=text,
            author_username=username,
            thread_context=thread_context or None,
            tone_examples=tone_examples or None,
        )
    except Exception as exc:
        print(f"  KI-Fehler: {exc}")
        return False

    draft_text = result["draft_text"]
    if len(draft_text) > 280:
        draft_text = draft_text[:277] + "..."

    if config.TELEGRAM_MODE:
        db.save_draft(
            tweet_id=tweet_id,
            author_username=username,
            original_text=text,
            draft_text=draft_text,
            context_analysis=result["context_analysis"],
        )
        db.mark_tweet_processed(tweet_id)
        print(f"  Entwurf an Telegram-Queue übergeben.")
        return True

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
        print(f"  Als 'pending' gespeichert – manuell über Review Queue posten.")
        return False

    db.save_draft(
        tweet_id=tweet_id,
        author_username=username,
        original_text=text,
        draft_text=draft_text,
        context_analysis=result["context_analysis"],
    )
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE drafts SET status = 'approved' WHERE tweet_id = ?", (tweet_id,)
        )
        conn.commit()
    db.mark_tweet_processed(tweet_id)
    print(f"  Geantwortet (ID: {new_tweet_id}): \"{draft_text[:60]}...\"")
    return True


def _process_dm(dm: dict) -> bool:
    dm_id = dm["dm_id"]
    username = dm["sender_username"]
    text = dm["text"]

    if _is_blacklisted(username):
        db.mark_dm_processed(dm_id)
        return False

    print(f"  [{_ts()}] DM von @{username}: \"{text[:70]}{'...' if len(text) > 70 else ''}\"")

    try:
        result = agent.generate_dm_reply(dm_text=text, sender_username=username)
    except Exception as exc:
        print(f"  KI-Fehler (DM): {exc}")
        return False

    draft_text = result["draft_text"]

    if config.TELEGRAM_MODE:
        db.save_dm_draft(
            dm_id=dm_id,
            sender_id=dm["sender_id"],
            sender_username=username,
            original_text=text,
            draft_text=draft_text,
            context_analysis=result["context_analysis"],
        )
        db.mark_dm_processed(dm_id)
        print(f"  DM-Entwurf an Telegram-Queue übergeben.")
        return True

    try:
        tc.reply_to_dm(dm["sender_id"], draft_text)
    except Exception as exc:
        print(f"  DM-Post-Fehler: {exc}")
        db.save_dm_draft(
            dm_id=dm_id,
            sender_id=dm["sender_id"],
            sender_username=username,
            original_text=text,
            draft_text=draft_text,
            context_analysis=result["context_analysis"],
        )
        db.mark_dm_processed(dm_id)
        return False

    db.save_dm_draft(
        dm_id=dm_id,
        sender_id=dm["sender_id"],
        sender_username=username,
        original_text=text,
        draft_text=draft_text,
        context_analysis=result["context_analysis"],
    )
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE dm_drafts SET status = 'approved' WHERE dm_id = ?", (dm_id,)
        )
        conn.commit()
    db.mark_dm_processed(dm_id)
    print(f"  DM-Antwort gesendet.")
    return True


def _poll_mentions():
    global _since_id
    try:
        mentions = tc.fetch_mentions(since_id=_since_id)
    except Exception as exc:
        print(f"  API-Fehler (Mentions): {exc}")
        return

    new_mentions = [m for m in mentions if not db.is_tweet_processed(m["tweet_id"])]

    if not new_mentions:
        print(f"  Keine neuen Mentions.")
        return

    print(f"  {len(new_mentions)} neue Mention(s):")
    for mention in new_mentions:
        if not _running:
            break
        _process_mention(mention)
        if len(new_mentions) > 1:
            time.sleep(2)

    if mentions:
        latest_id = max(int(m["tweet_id"]) for m in mentions)
        _since_id = str(latest_id)


def _poll_dms():
    global _since_dm_id
    try:
        dms = tc.fetch_dms(since_id=_since_dm_id)
    except Exception as exc:
        print(f"  API-Fehler (DMs): {exc}")
        return

    new_dms = [d for d in dms if not db.is_dm_processed(d["dm_id"])]

    if not new_dms:
        return

    print(f"  {len(new_dms)} neue DM(s):")
    for dm in new_dms:
        if not _running:
            break
        _process_dm(dm)
        time.sleep(1)

    if new_dms:
        _since_dm_id = max(d["dm_id"] for d in new_dms)


def run_auto_mode():
    global _running
    _running = True

    signal.signal(signal.SIGINT, _signal_handler)

    mode_info = []
    if config.KEYWORD_FILTER:
        mode_info.append(f"Keywords: {', '.join(config.KEYWORD_FILTER)}")
    if config.BLACKLIST:
        mode_info.append(f"Blacklist: {len(config.BLACKLIST)} Account(s)")
    if config.QUIET_HOURS_START != config.QUIET_HOURS_END:
        mode_info.append(f"Quiet Hours: {config.QUIET_HOURS_START}–{config.QUIET_HOURS_END} Uhr")
    if config.DMS_ENABLED:
        mode_info.append("DMs: aktiv")
    if config.TELEGRAM_MODE:
        mode_info.append("Telegram-Review: aktiv (kein Auto-Post)")
    if config.TONE_TWEET_COUNT > 0:
        mode_info.append(f"Tone-of-Voice: {config.TONE_TWEET_COUNT} Beispiel-Tweets")

    print(f"\n  Auto-Modus gestartet. Polling alle {config.POLL_INTERVAL}s | Stoppen: Ctrl+C")
    if mode_info:
        print(f"  Aktive Filter: {' | '.join(mode_info)}")
    print(f"  {'─' * 56}")

    while _running:
        print(f"\n  [{_ts()}] Prüfe auf neue Nachrichten ...")

        if _is_quiet_hours():
            print(f"  Quiet Hours aktiv ({config.QUIET_HOURS_START}–{config.QUIET_HOURS_END} Uhr). Überspringe.")
        else:
            _poll_mentions()
            if config.DMS_ENABLED:
                _poll_dms()

        if _running:
            _wait(config.POLL_INTERVAL)

    print(f"\n  [{_ts()}] Auto-Modus beendet.")


def _wait(seconds: int):
    global _running
    for _ in range(seconds):
        if not _running:
            break
        time.sleep(1)
