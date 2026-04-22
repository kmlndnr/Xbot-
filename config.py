import os
from dotenv import load_dotenv

load_dotenv()


def _list(env_var: str) -> list[str]:
    raw = os.getenv(env_var, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# Polling
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))

# Filter
KEYWORD_FILTER: list[str] = [k.lower() for k in _list("KEYWORD_FILTER")]
BLACKLIST: list[str] = [u.lower().lstrip("@") for u in _list("BLACKLIST_ACCOUNTS")]

# Quiet Hours
QUIET_HOURS_START: int = int(os.getenv("QUIET_HOURS_START", "23"))
QUIET_HOURS_END: int = int(os.getenv("QUIET_HOURS_END", "7"))

# Tone-of-Voice
TONE_TWEET_COUNT: int = int(os.getenv("TONE_TWEET_COUNT", "10"))

# DMs
DMS_ENABLED: bool = os.getenv("DMS_ENABLED", "false").lower() == "true"

# Reactions
AUTO_LIKE_MENTIONS: bool = os.getenv("AUTO_LIKE_MENTIONS", "false").lower() == "true"
AUTO_RETWEET_MENTIONS: bool = os.getenv("AUTO_RETWEET_MENTIONS", "false").lower() == "true"

# Sentiment-Filter: Mentions mit diesen Sentiments überspringen
# Mögliche Werte: positive, neutral, negative, aggressive
SENTIMENT_BLOCK: list[str] = [s.lower() for s in _list("SENTIMENT_BLOCK")]

# Follower
WELCOME_NEW_FOLLOWERS: bool = os.getenv("WELCOME_NEW_FOLLOWERS", "false").lower() == "true"
WELCOME_DM_TEXT: str = os.getenv(
    "WELCOME_DM_TEXT",
    "Hey {username}! Danke, dass du mir folgst 👋 Freue mich auf den Austausch!"
)

# Telegram
TELEGRAM_MODE: bool = os.getenv("TELEGRAM_MODE", "false").lower() == "true"
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Web Dashboard
WEB_PORT: int = int(os.getenv("WEB_PORT", "5000"))
WEB_SECRET_KEY: str = os.getenv("WEB_SECRET_KEY", "change-me-in-production")
