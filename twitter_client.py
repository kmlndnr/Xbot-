import os
import tweepy
from dotenv import load_dotenv

load_dotenv()


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
        consumer_key=os.getenv("TWITTER_API_KEY"),
        consumer_secret=os.getenv("TWITTER_API_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_SECRET"),
        wait_on_rate_limit=True,
    )


def get_my_user_id(client: tweepy.Client) -> str:
    user_id = os.getenv("TWITTER_USER_ID", "").strip()
    if user_id:
        return user_id
    me = client.get_me()
    if not me.data:
        raise RuntimeError("Konnte eigene User-ID nicht abrufen. Prüfe deine API-Credentials.")
    return str(me.data.id)


def fetch_mentions(since_id: str | None = None) -> list[dict]:
    """
    Gibt eine Liste von Mentions zurück.
    Jedes Element: {tweet_id, author_id, author_username, text, conversation_id, in_reply_to_tweet_id}
    """
    client = _get_client()
    user_id = get_my_user_id(client)

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


def fetch_thread_context(conversation_id: str, exclude_tweet_id: str) -> list[str]:
    """
    Holt die letzten Tweets eines Threads als Kontextliste.
    Gibt eine Liste von Tweet-Texten zurück (älteste zuerst).
    """
    if not conversation_id:
        return []
    try:
        client = _get_client()
        query = f"conversation_id:{conversation_id} -is:retweet"
        response = client.search_recent_tweets(
            query=query,
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

        thread = []
        for tweet in reversed(response.data):
            if str(tweet.id) == exclude_tweet_id:
                continue
            username = users_by_id.get(str(tweet.author_id), "unknown")
            thread.append(f"@{username}: {tweet.text}")
        return thread
    except Exception:
        return []


def fetch_user_timeline(count: int = 10) -> list[str]:
    """
    Holt die eigenen letzten Tweets als Ton-Beispiele für den System-Prompt.
    """
    try:
        client = _get_client()
        user_id = get_my_user_id(client)
        response = client.get_users_tweets(
            id=user_id,
            max_results=min(count, 100),
            tweet_fields=["text"],
            exclude=["retweets", "replies"],
        )
        if not response.data:
            return []
        return [tweet.text for tweet in response.data]
    except Exception:
        return []


def fetch_dms(since_id: str | None = None) -> list[dict]:
    """
    Holt neue Direktnachrichten.
    Jedes Element: {dm_id, sender_id, sender_username, text}
    Benötigt dm.read OAuth-Scope.
    """
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

        results = []
        for event in response.data:
            sender_id = str(event.sender_id)
            # Eigene Nachrichten überspringen
            if sender_id == user_id:
                continue
            results.append({
                "dm_id": str(event.id),
                "sender_id": sender_id,
                "sender_username": users_by_id.get(sender_id, "unknown"),
                "text": event.text,
            })
        return results
    except Exception as exc:
        print(f"  DM-Fehler: {exc}")
        return []


def reply_to_dm(recipient_id: str, text: str) -> str:
    """Sendet eine DM und gibt die neue Event-ID zurück. Benötigt dm.write Scope."""
    client = _get_client()
    response = client.create_direct_message(
        participant_id=recipient_id,
        text=text,
    )
    if not response.data:
        raise RuntimeError("DM konnte nicht gesendet werden.")
    return str(response.data["dm_conversation_id"])


def post_reply(reply_text: str, in_reply_to_tweet_id: str) -> str:
    """Postet einen Reply und gibt die neue Tweet-ID zurück."""
    client = _get_client()
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
    )
    if not response.data:
        raise RuntimeError("Tweet konnte nicht gepostet werden.")
    return str(response.data["id"])
