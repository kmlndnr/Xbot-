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
    Gibt eine Liste von Mentions zurück, die noch nicht beantwortet wurden.
    Jedes Element: {tweet_id, author_id, author_username, text}
    """
    client = _get_client()
    user_id = get_my_user_id(client)

    kwargs = {
        "id": user_id,
        "tweet_fields": ["author_id", "text", "in_reply_to_user_id", "created_at"],
        "expansions": ["author_id"],
        "user_fields": ["username"],
        "max_results": 10,
    }
    if since_id:
        kwargs["since_id"] = since_id

    response = client.get_users_mentions(**kwargs)

    if not response.data:
        return []

    # Benutzernamen aus den includes herauslesen
    users_by_id = {}
    if response.includes and "users" in response.includes:
        for user in response.includes["users"]:
            users_by_id[str(user.id)] = user.username

    results = []
    for tweet in response.data:
        results.append({
            "tweet_id": str(tweet.id),
            "author_id": str(tweet.author_id),
            "author_username": users_by_id.get(str(tweet.author_id), "unknown"),
            "text": tweet.text,
        })
    return results


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
