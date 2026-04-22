import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

SENTIMENTS = ("positive", "neutral", "negative", "aggressive")


def analyze(text: str) -> str:
    """
    Klassifiziert den Sentiment eines Tweets.
    Gibt einen von 4 Werten zurück: positive, neutral, negative, aggressive
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5,
        system=(
            "Classify the sentiment of this social media message as exactly one of: "
            "positive, neutral, negative, aggressive. "
            "aggressive = insults, hate speech, trolling. "
            "Reply with only that single word, nothing else."
        ),
        messages=[{"role": "user", "content": text}],
    )
    result = response.content[0].text.strip().lower()
    return result if result in SENTIMENTS else "neutral"


def should_skip(text: str, blocked_sentiments: list[str]) -> tuple[bool, str]:
    """
    Prüft ob ein Tweet übersprungen werden soll.
    Gibt (skip: bool, sentiment: str) zurück.
    """
    if not blocked_sentiments:
        return False, "neutral"
    sentiment = analyze(text)
    return sentiment in blocked_sentiments, sentiment
