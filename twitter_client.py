import os
import tweepy
from dotenv import load_dotenv

load_dotenv()


def _get_client(creds: dict | None = None) -> tweepy.Client:
    c = creds or {}
    return tweepy.Client(
        bearer_token=c.get("bearer_token") or os.getenv("TWITTER_BEARER_TOKEN"),
        consumer_key=c.get("api_key") or os.getenv("TWITTER_API_KEY"),
        consumer_secret=c.get("api_secret") or os.getenv("TWITTER_API_SECRET"),
        access_token=c.get("access_token") or os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=c.get("access_secret") or os.getenv("TWITTER_ACCESS_SECRET"),
        wait_on_rate_limit=True,
    )


def get_my_user_id(client: tweepy.Client, creds: dict | None = None) -> str:
    user_id = (creds or {}).get("user_id") or os.getenv("TWITTER_USER_ID", "").strip()
    if user_id:
        return user_id
    me = client.get_me()
    if not me.data:
        raise RuntimeError("Konnte eigene User-ID nicht abrufen.")
    return str(me.data.id)


# ── Mentions ──────────────────────────────────────────────────────────────────

def _fetch_mentions_impl(client: tweepy.Client, user_id: str,
                         since_id: str | None) -> list[dict]:
    kwargs = {
        "id": user_id,
        "tweet_fields": ["author_id", "text", "in_reply_to_user_id",
                         "conversation_id", "referenced_tweets", "created_at"],
        "expansions": ["author_id", "referenced_tweets.id"],
        "user_fields": ["username"],
        "max_results": 10,
    }
    if since_id:
        kwargs["since_id"] = since_id

    response = client.get_users_mentions(**kwargs)
    if not response.data:
        return []

    users_by_id = {}
    if response.includes and "users" in response.includes:
        for user in response.includes["users"]:
            users_by_id[str(user.id)] = user.username

    results = []
    for tweet in response.data:
        in_reply_to = None
        if tweet.referenced_tweets:
            for ref in tweet.referenced_tweets:
                if ref.type == "replied_to":
                    in_reply_to = str(ref.id)
                    break
        results.append({
            "tweet_id": str(tweet.id),
            "author_id": str(tweet.author_id),
            "author_username": users_by_id.get(str(tweet.author_id), "unknown"),
            "text": tweet.text,
            "conversation_id": str(tweet.conversation_id) if tweet.conversation_id else None,
            "in_reply_to_tweet_id": in_reply_to,
        })
    return results


def fetch_mentions(since_id: str | None = None) -> list[dict]:
    client = _get_client()
    user_id = get_my_user_id(client)
    return _fetch_mentions_impl(client, user_id, since_id)


def fetch_mentions_with_creds(creds: dict, since_id: str | None = None) -> list[dict]:
    client = _get_client(creds)
    user_id = get_my_user_id(client, creds)
    return _fetch_mentions_impl(client, user_id, since_id)


# ── Thread & Timeline ─────────────────────────────────────────────────────────

def fetch_thread_context(conversation_id: str, exclude_tweet_id: str) -> list[str]:
    if not conversation_id:
        return []
    try:
        client = _get_client()
        response = client.search_recent_tweets(
            query=f"conversation_id:{conversation_id} -is:retweet",
            tweet_fields=["text", "author_id", "created_at"],
            expansions=["author_id"],
            user_fields=["username"],
            max_results=10,
        )
        if not response.data:
            return []

        users_by_id = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users_by_id[str(user.id)] = user.username

        return [
            f"@{users_by_id.get(str(t.author_id), 'unknown')}: {t.text}"
            for t in reversed(response.data)
            if str(t.id) != exclude_tweet_id
        ]
    except Exception:
        return []


def fetch_user_timeline(count: int = 10) -> list[str]:
    try:
        client = _get_client()
        user_id = get_my_user_id(client)
        response = client.get_users_tweets(
            id=user_id,
            max_results=min(count, 100),
            tweet_fields=["text"],
            exclude=["retweets", "replies"],
        )
        return [tweet.text for tweet in response.data] if response.data else []
    except Exception:
        return []


# ── Reactions: Like & Retweet ─────────────────────────────────────────────────

def like_tweet(tweet_id: str) -> bool:
    try:
        client = _get_client()
        user_id = get_my_user_id(client)
        client.like(user_id, tweet_id)
        return True
    except Exception:
        return False


def like_tweet_with_creds(creds: dict, tweet_id: str) -> bool:
    try:
        client = _get_client(creds)
        user_id = get_my_user_id(client, creds)
        client.like(user_id, tweet_id)
        return True
    except Exception:
        return False


def retweet(tweet_id: str) -> bool:
    try:
        client = _get_client()
        user_id = get_my_user_id(client)
        client.retweet(user_id, tweet_id)
        return True
    except Exception:
        return False


def retweet_with_creds(creds: dict, tweet_id: str) -> bool:
    try:
        client = _get_client(creds)
        user_id = get_my_user_id(client, creds)
        client.retweet(user_id, tweet_id)
        return True
    except Exception:
        return False


# ── Follower ──────────────────────────────────────────────────────────────────

def fetch_followers(max_results: int = 100) -> list[dict]:
    """Gibt aktuelle Follower als Liste zurück: {follower_id, username}"""
    try:
        client = _get_client()
        user_id = get_my_user_id(client)
        response = client.get_users_followers(
            id=user_id,
            max_results=max_results,
            user_fields=["username"],
        )
        if not response.data:
            return []
        return [{"follower_id": str(u.id), "username": u.username}
                for u in response.data]
    except Exception as exc:
        print(f"  fetch_followers Fehler: {exc}")
        return []


# ── DMs ───────────────────────────────────────────────────────────────────────

def fetch_dms(since_id: str | None = None) -> list[dict]:
    try:
        client = _get_client()
        user_id = get_my_user_id(client)

        kwargs = {
            "dm_event_fields": ["id", "text", "sender_id", "created_at"],
            "expansions": ["sender_id"],
            "user_fields": ["username"],
            "max_results": 5,
        }
        if since_id:
            kwargs["since_id"] = since_id

        response = client.get_dm_events(**kwargs)
        if not response.data:
            return []

        users_by_id = {}
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users_by_id[str(user.id)] = user.username

        return [
            {
                "dm_id": str(e.id),
                "sender_id": str(e.sender_id),
                "sender_username": users_by_id.get(str(e.sender_id), "unknown"),
                "text": e.text,
            }
            for e in response.data
            if str(e.sender_id) != user_id
        ]
    except Exception as exc:
        print(f"  DM-Fehler: {exc}")
        return []


def reply_to_dm(recipient_id: str, text: str) -> str:
    client = _get_client()
    response = client.create_direct_message(participant_id=recipient_id, text=text)
    if not response.data:
        raise RuntimeError("DM konnte nicht gesendet werden.")
    return str(response.data["dm_conversation_id"])


# ── Posting ───────────────────────────────────────────────────────────────────

def post_reply(reply_text: str, in_reply_to_tweet_id: str) -> str:
    client = _get_client()
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
    )
    if not response.data:
        raise RuntimeError("Tweet konnte nicht gepostet werden.")
    return str(response.data["id"])


def post_reply_with_creds(creds: dict, reply_text: str,
                           in_reply_to_tweet_id: str) -> str:
    client = _get_client(creds)
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
    )
    if not response.data:
        raise RuntimeError("Tweet konnte nicht gepostet werden.")
    return str(response.data["id"])
