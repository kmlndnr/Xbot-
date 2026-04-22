import os
from dotenv import load_dotenv

load_dotenv()


def _list(env_var: str) -> list[str]:
    raw = os.getenv(env_var, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# Polling
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))

# Filter: nur auf Mentions reagieren, die mind. eines dieser Wörter enthalten.
# Leer = alle Mentions bearbeiten.
KEYWORD_FILTER: list[str] = [k.lower() for k in _list("KEYWORD_FILTER")]

# Blacklist: diese Accounts werden komplett ignoriert (ohne @)
BLACKLIST: list[str] = [u.lower().lstrip("@") for u in _list("BLACKLIST_ACCOUNTS")]

# Quiet Hours: zwischen START und END (Stunden, 0-23) wird nicht gepostet
QUIET_HOURS_START: int = int(os.getenv("QUIET_HOURS_START", "23"))
QUIET_HOURS_END: int = int(os.getenv("QUIET_HOURS_END", "7"))

# Tone-of-Voice: Anzahl eigener Tweets, die als Stil-Beispiele geladen werden
TONE_TWEET_COUNT: int = int(os.getenv("TONE_TWEET_COUNT", "10"))

# DM-Verarbeitung
DMS_ENABLED: bool = os.getenv("DMS_ENABLED", "false").lower() == "true"

# Telegram Review
TELEGRAM_MODE: bool = os.getenv("TELEGRAM_MODE", "false").lower() == "true"
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Web Dashboard
WEB_PORT: int = int(os.getenv("WEB_PORT", "5000"))
WEB_SECRET_KEY: str = os.getenv("WEB_SECRET_KEY", "change-me-in-production")
