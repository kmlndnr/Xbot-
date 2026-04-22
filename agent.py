import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Passe diesen Prompt an deine Persönlichkeit und deine Produkte an ──────────
_BASE_SYSTEM_PROMPT = """Du bist mein digitaler Zwilling und Social-Media-Assistent.
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


def _build_system_prompt(tone_examples: list[str] | None) -> str:
    if not tone_examples:
        return _BASE_SYSTEM_PROMPT

    examples_block = "\n".join(f'- "{t}"' for t in tone_examples[:10])
    tone_section = f"""

Mein Schreibstil – lerne daraus, wie ich kommuniziere:
{examples_block}"""
    return _BASE_SYSTEM_PROMPT + tone_section


def generate_draft(
    tweet_text: str,
    author_username: str,
    thread_context: list[str] | None = None,
    tone_examples: list[str] | None = None,
) -> dict:
    """
    Sendet die Mention an Claude und gibt ein dict mit
    {draft_text, context_analysis} zurück.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = _build_system_prompt(tone_examples)

    # Kontext-Block aufbauen
    context_parts = []
    if thread_context:
        context_parts.append("Thread-Verlauf (älteste zuerst):\n" +
                             "\n".join(f"  {line}" for line in thread_context))
    context_parts.append(f"Neueste Nachricht von @{author_username}:\n\"{tweet_text}\"")

    user_message = "\n\n".join(context_parts)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
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


def generate_dm_reply(dm_text: str, sender_username: str) -> dict:
    """Generiert eine DM-Antwort. Kein 280-Zeichen-Limit."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    dm_prompt = _BASE_SYSTEM_PROMPT.replace(
        "3. Halte Antworten unter 280 Zeichen (Twitter-Limit).",
        "3. DMs dürfen länger sein – max. 500 Zeichen.",
    ).replace(
        '"type": "reply"',
        '"type": "dm_reply"',
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=dm_prompt,
        messages=[{"role": "user", "content":
                   f"Direktnachricht von @{sender_username}:\n\"{dm_text}\""}],
    )

    raw = message.content[0].text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        parsed = json.loads(raw[start:end]) if start != -1 and end > start else {}

    return {
        "draft_text": parsed.get("draft_text", ""),
        "context_analysis": parsed.get("context_analysis", ""),
    }
