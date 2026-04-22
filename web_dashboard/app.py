import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

import db
import twitter_client as tc
import config

app = Flask(__name__)
app.secret_key = config.WEB_SECRET_KEY


@app.route("/")
def index():
    return render_template("index.html",
                           pending=db.get_pending_drafts(),
                           pending_dms=db.get_pending_dm_drafts(),
                           scheduled=db.get_scheduled_tweets(),
                           stats=db.get_stats())


@app.route("/history")
def history():
    return render_template("index.html",
                           pending=[],
                           pending_dms=[],
                           scheduled=[],
                           stats=db.get_stats(),
                           history=db.get_all_drafts(limit=100))


# ── Draft Actions ──────────────────────────────────────────────────────────────

@app.route("/api/draft/<int:draft_id>/approve", methods=["POST"])
def approve_draft(draft_id):
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Nicht gefunden"}), 404
    try:
        tweet_id = tc.post_reply(draft["draft_text"], draft["tweet_id"])
        db.update_draft_status(draft_id, "approved")
        return jsonify({"ok": True, "tweet_id": tweet_id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/draft/<int:draft_id>/reject", methods=["POST"])
def reject_draft(draft_id):
    if not db.get_draft_by_id(draft_id):
        return jsonify({"ok": False, "error": "Nicht gefunden"}), 404
    db.update_draft_status(draft_id, "rejected")
    return jsonify({"ok": True})


@app.route("/api/draft/<int:draft_id>/approve_edited", methods=["POST"])
def approve_edited(draft_id):
    new_text = request.json.get("text", "").strip()
    if not new_text:
        return jsonify({"ok": False, "error": "Kein Text"}), 400
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Nicht gefunden"}), 404
    try:
        tweet_id = tc.post_reply(new_text, draft["tweet_id"])
        db.update_draft_status(draft_id, "approved", new_text=new_text)
        return jsonify({"ok": True, "tweet_id": tweet_id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Scheduler ─────────────────────────────────────────────────────────────────

@app.route("/api/schedule", methods=["POST"])
def schedule_tweet():
    data = request.json or {}
    text = data.get("text", "").strip()
    scheduled_at = data.get("scheduled_at", "").strip()
    account_name = data.get("account_name", "main")

    if not text:
        return jsonify({"ok": False, "error": "Kein Text"}), 400
    if not scheduled_at:
        return jsonify({"ok": False, "error": "Kein Zeitpunkt"}), 400
    if len(text) > 280:
        return jsonify({"ok": False, "error": "Text zu lang (max 280)"}), 400

    tweet_id = db.create_scheduled_tweet(text, scheduled_at, account_name)
    return jsonify({"ok": True, "id": tweet_id})


@app.route("/api/schedule/<int:tweet_id>/cancel", methods=["POST"])
def cancel_scheduled(tweet_id):
    db.cancel_scheduled_tweet(tweet_id)
    return jsonify({"ok": True})


@app.route("/api/schedule", methods=["GET"])
def get_scheduled():
    tweets = db.get_scheduled_tweets()
    return jsonify([dict(t) for t in tweets])


# ── Stats & General ────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_stats())


def run():
    app.run(host="0.0.0.0", port=config.WEB_PORT, debug=False)


if __name__ == "__main__":
    db.init_db()
    run()
