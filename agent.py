import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Passe diesen Prompt an deine Persönlichkeit und deine Produkte an ──────────
SYSTEM_PROMPT = """Du bist mein digitaler Zwilling und Social-Media-Assistent.
Antworte auf den folgenden Tweet in meinem Namen – authentisch, direkt und auf den Punkt.

Meine Persönlichkeit: [HIER DEINE PERSÖNLICHKEIT BESCHREIBEN – z.B. "Ich bin ein Tech-Unternehmer, der über KI und Automatisierung schreibt."]

Meine Produkte/Angebote:
- [PRODUKT 1: z.B. "AI Automation Kurs – hilft Unternehmern, repetitive Aufgaben zu automatisieren"]
- [PRODUKT 2: z.B. "1:1 Consulting für KI-Strategie"]

Regeln:
1. Antworte in der gleichen Sprache wie der Original-Tweet.
2. Binde ein Produkt NUR organisch ein, wenn es thematisch wirklich passt – niemals aufgesetzt.
3. Halte Antworten unter 280 Zeichen (Twitter-Limit).
4. Sei menschlich, nicht roboterhaft.
5. Antworte AUSSCHLIESSLICH in diesem JSON-Format, ohne Markdown-Blöcke:

{"type": "reply", "context_analysis": "Kurze Analyse des Tweets und warum diese Antwort passt.", "draft_text": "Der fertige Antwort-Text für Twitter."}"""
# ──────────────────────────────────────────────────────────────────────────────


def generate_draft(tweet_text: str, author_username: str) -> dict:
    """
    Sendet die Mention an Claude und gibt ein dict mit
    {draft_text, context_analysis} zurück.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_message = f"@{author_username} hat geschrieben:\n\n\"{tweet_text}\""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # JSON aus der Antwort parsen – robustes Fallback falls Modell Markdown hinzufügt
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Versuche JSON-Block aus Markdown-Wrapper zu extrahieren
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(raw[start:end])
        else:
            raise ValueError(f"Konnte kein JSON aus der KI-Antwort parsen:\n{raw}")

    return {
        "draft_text": parsed.get("draft_text", ""),
        "context_analysis": parsed.get("context_analysis", ""),
    }
