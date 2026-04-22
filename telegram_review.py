"""
Telegram Review Bot – läuft parallel zum Auto-Modus.
Starten: python telegram_review.py

Benötigt in .env:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
  TELEGRAM_MODE=true

Befehle:
  /queue  – Alle pending Entwürfe anzeigen
  /stats  – Statistiken
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import db
import twitter_client as tc
import config

logging.basicConfig(level=logging.WARNING)

EDIT_STATE = 1
_edit_context: dict = {}  # draft_id -> chat_id


def _authorized(update: Update) -> bool:
    chat_id = str(update.effective_chat.id)
    return chat_id == config.TELEGRAM_CHAT_ID


def _draft_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Freigeben", callback_data=f"approve:{draft_id}"),
            InlineKeyboardButton("❌ Ablehnen", callback_data=f"reject:{draft_id}"),
            InlineKeyboardButton("✏️ Bearbeiten", callback_data=f"edit:{draft_id}"),
        ]
    ])


def _dm_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Senden", callback_data=f"dm_approve:{draft_id}"),
            InlineKeyboardButton("❌ Ablehnen", callback_data=f"dm_reject:{draft_id}"),
        ]
    ])


def _format_draft_message(draft) -> str:
    char_count = len(draft["draft_text"])
    indicator = "🟢" if char_count <= 280 else "🔴"
    lines = [
        f"📥 *Mention von @{draft['author_username']}*",
        f"_{draft['created_at'][:16]}_",
        "",
        "📌 *Original:*",
        f"`{draft['original_text'][:200]}`",
    ]
    if draft["context_analysis"]:
        lines += ["", f"💡 _{draft['context_analysis'][:150]}_"]
    lines += [
        "",
        "✍️ *Entwurf:*",
        f"{draft['draft_text']}",
        "",
        f"{indicator} {char_count}/280 Zeichen",
    ]
    return "\n".join(lines)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    pending = db.get_pending_drafts()
    await update.message.reply_text(
        f"👋 Xbot aktiv.\n\n"
        f"📋 Pending: *{len(pending)}* Entwurf/Entwürfe\n\n"
        f"Befehle:\n/queue – Entwürfe anzeigen\n/stats – Statistiken",
        parse_mode="Markdown"
    )


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return

    pending = db.get_pending_drafts()
    if not pending:
        await update.message.reply_text("✅ Keine ausstehenden Entwürfe.")
        return

    await update.message.reply_text(f"📋 *{len(pending)} Entwurf/Entwürfe:*", parse_mode="Markdown")

    for draft in pending[:5]:  # max 5 auf einmal
        try:
            await update.message.reply_text(
                _format_draft_message(draft),
                parse_mode="Markdown",
                reply_markup=_draft_keyboard(draft["id"])
            )
        except Exception as exc:
            await update.message.reply_text(f"Fehler bei Entwurf #{draft['id']}: {exc}")

    if len(pending) > 5:
        await update.message.reply_text(f"... und {len(pending) - 5} weitere. Erneut /queue für mehr.")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    s = db.get_stats()
    rate = (s["approved"] / s["total"] * 100) if s["total"] > 0 else 0
    msg = (
        f"📊 *Statistiken*\n\n"
        f"Gesamt: {s['total']}\n"
        f"✅ Approved: {s['approved']}\n"
        f"❌ Rejected: {s['rejected']}\n"
        f"⏳ Pending: {s['pending']}\n"
        f"📈 Approval-Rate: {rate:.1f}%\n"
    )
    if s["top_mentioners"]:
        msg += "\n🏆 *Top Erwähner:*\n"
        for r in s["top_mentioners"][:3]:
            msg += f"  @{r['author_username']} – {r['cnt']}x\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not _authorized(update):
        return

    action, draft_id_str = query.data.split(":", 1)
    draft_id = int(draft_id_str)

    if action == "approve":
        draft = db.get_draft_by_id(draft_id)
        if not draft:
            await query.edit_message_text("❌ Entwurf nicht gefunden.")
            return
        try:
            tweet_id = tc.post_reply(draft["draft_text"], draft["tweet_id"])
            db.update_draft_status(draft_id, "approved")
            await query.edit_message_text(
                f"✅ Gepostet!\nTweet-ID: `{tweet_id}`", parse_mode="Markdown"
            )
        except Exception as exc:
            await query.edit_message_text(f"❌ Fehler: {exc}")

    elif action == "reject":
        db.update_draft_status(draft_id, "rejected")
        await query.edit_message_text("❌ Entwurf abgelehnt.")

    elif action == "edit":
        _edit_context[draft_id] = query.message.chat_id
        await query.edit_message_text(
            f"✏️ Schick mir den neuen Text für Entwurf #{draft_id}.\n\n"
            f"Abbrechen: /cancel",
            parse_mode="Markdown"
        )
        ctx.user_data["editing_draft_id"] = draft_id
        return EDIT_STATE

    elif action == "dm_approve":
        draft = db.get_pending_dm_drafts()
        dm_draft = next((d for d in draft if d["id"] == draft_id), None)
        if not dm_draft:
            await query.edit_message_text("❌ DM-Entwurf nicht gefunden.")
            return
        try:
            tc.reply_to_dm(dm_draft["sender_id"], dm_draft["draft_text"])
            db.update_dm_draft_status(draft_id, "approved")
            await query.edit_message_text("✅ DM gesendet!")
        except Exception as exc:
            await query.edit_message_text(f"❌ Fehler: {exc}")

    elif action == "dm_reject":
        db.update_dm_draft_status(draft_id, "rejected")
        await query.edit_message_text("❌ DM-Entwurf abgelehnt.")


async def receive_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return ConversationHandler.END

    draft_id = ctx.user_data.get("editing_draft_id")
    if not draft_id:
        return ConversationHandler.END

    new_text = update.message.text.strip()
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        await update.message.reply_text("❌ Entwurf nicht mehr vorhanden.")
        return ConversationHandler.END

    char_count = len(new_text)
    indicator = "🟢" if char_count <= 280 else "🔴"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ So posten", callback_data=f"approve:{draft_id}"),
            InlineKeyboardButton("❌ Verwerfen", callback_data=f"reject:{draft_id}"),
        ]
    ])

    db.update_draft_status(draft_id, "pending", new_text=new_text)
    await update.message.reply_text(
        f"✏️ Aktualisiert ({indicator} {char_count}/280):\n\n{new_text}",
        reply_markup=keyboard
    )
    ctx.user_data.pop("editing_draft_id", None)
    return ConversationHandler.END


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("editing_draft_id", None)
    await update.message.reply_text("Abgebrochen.")
    return ConversationHandler.END


async def notify_new_draft(app: Application, draft_id: int):
    """Sendet eine Benachrichtigung für einen neuen Entwurf."""
    if not config.TELEGRAM_CHAT_ID:
        return
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return
    try:
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=_format_draft_message(draft),
            parse_mode="Markdown",
            reply_markup=_draft_keyboard(draft_id)
        )
    except Exception as exc:
        print(f"  Telegram-Benachrichtigung fehlgeschlagen: {exc}")


def build_app() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN fehlt in der .env")

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^edit:")],
        states={EDIT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("queue", cmd_queue))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(callback_handler))

    return application


def run():
    db.init_db()
    print("  Telegram Bot gestartet. Warte auf Nachrichten ...")
    print(f"  Chat-ID: {config.TELEGRAM_CHAT_ID or '(nicht gesetzt)'}")
    app = build_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run()
