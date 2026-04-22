import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

import db
import twitter_client as tc
import config

app = Flask(__name__)
app.secret_key = config.WEB_SECRET_KEY


@app.route("/")
def index():
    pending = db.get_pending_drafts()
    stats = db.get_stats()
    pending_dms = db.get_pending_dm_drafts()
    return render_template("index.html",
                           pending=pending,
                           pending_dms=pending_dms,
                           stats=stats)


@app.route("/history")
def history():
    drafts = db.get_all_drafts(limit=100)
    return render_template("index.html",
                           pending=[],
                           pending_dms=[],
                           stats=db.get_stats(),
                           history=drafts)


@app.route("/api/draft/<int:draft_id>/approve", methods=["POST"])
def approve_draft(draft_id):
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Draft nicht gefunden"}), 404
    try:
        tweet_id = tc.post_reply(draft["draft_text"], draft["tweet_id"])
        db.update_draft_status(draft_id, "approved")
        return jsonify({"ok": True, "tweet_id": tweet_id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/draft/<int:draft_id>/reject", methods=["POST"])
def reject_draft(draft_id):
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Draft nicht gefunden"}), 404
    db.update_draft_status(draft_id, "rejected")
    return jsonify({"ok": True})


@app.route("/api/draft/<int:draft_id>/edit", methods=["POST"])
def edit_draft(draft_id):
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Draft nicht gefunden"}), 404
    new_text = request.json.get("text", "").strip()
    if not new_text:
        return jsonify({"ok": False, "error": "Kein Text angegeben"}), 400
    db.update_draft_status(draft_id, "pending", new_text=new_text)
    return jsonify({"ok": True})


@app.route("/api/draft/<int:draft_id>/approve_edited", methods=["POST"])
def approve_edited(draft_id):
    new_text = request.json.get("text", "").strip()
    if not new_text:
        return jsonify({"ok": False, "error": "Kein Text angegeben"}), 400
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        return jsonify({"ok": False, "error": "Draft nicht gefunden"}), 404
    try:
        tweet_id = tc.post_reply(new_text, draft["tweet_id"])
        db.update_draft_status(draft_id, "approved", new_text=new_text)
        return jsonify({"ok": True, "tweet_id": tweet_id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_stats())


def run():
    app.run(host="0.0.0.0", port=config.WEB_PORT, debug=False)


if __name__ == "__main__":
    db.init_db()
    run()
