import os
import tempfile
from flask import Flask, request, jsonify, render_template
from locketlam import LocketClient, NoteType
from locketlam.exceptions import LocketError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "locketlam_session.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # Hỗ trợ tối đa 100MB media

client = LocketClient(session_path=SESSION_FILE)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    authed = client.is_authenticated()
    profile = None
    if authed:
        try:
            profile = client.user.get_profile()
        except Exception:
            profile = None
    return jsonify({
        "authenticated": authed,
        "uid": client.session.uid if authed else None,
        "profile": profile
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Vui lòng nhập đầy đủ email và mật khẩu."}), 400
    try:
        client.login(email, password)
        return jsonify({"ok": True, "uid": client.session.uid})
    except LocketError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi đăng nhập: {e}"}), 500


@app.route("/api/friends", methods=["GET"])
def api_friends():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    try:
        friends = client.friends.get_all_friends()
        return jsonify({"ok": True, "friends": friends})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/post", methods=["POST"])
def api_post():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập session Locket."}), 401

    temp_files = []
    try:
        caption = (request.form.get("caption") or "").strip()
        note_type = (request.form.get("note_type") or NoteType.STANDARD).strip()
        icon = (request.form.get("icon") or "").strip() or None
        color_start = (request.form.get("color_start") or "").strip()
        color_end = (request.form.get("color_end") or "").strip()
        text_color = (request.form.get("text_color") or "").strip() or None
        is_private = request.form.get("is_private") == "true"
        image_url = (request.form.get("image_url") or "").strip()

        recipients_raw = (request.form.get("recipients") or "").strip()
        recipients = [u.strip() for u in recipients_raw.split(",") if u.strip()] if recipients_raw else None

        colors = None
        if color_start and color_end:
            colors = [color_start, color_end]
        elif color_start:
            colors = [color_start]

        image_input = None
        video_input = None

        img_file = request.files.get("image")
        vid_file = request.files.get("video")

        if img_file and img_file.filename:
            ext = os.path.splitext(img_file.filename)[1] or ".jpg"
            fd, tmp_img = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            img_file.save(tmp_img)
            temp_files.append(tmp_img)
            image_input = tmp_img
        elif image_url:
            image_input = image_url

        if vid_file and vid_file.filename:
            ext = os.path.splitext(vid_file.filename)[1] or ".mp4"
            fd, tmp_vid = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            vid_file.save(tmp_vid)
            temp_files.append(tmp_vid)
            video_input = tmp_vid

        if not image_input and not video_input:
            return jsonify({"ok": False, "error": "Vui lòng chọn ảnh, link ảnh hoặc video để đăng."}), 400

        result = client.moments.post(
            image=image_input,
            video=video_input,
            caption=caption,
            note_type=note_type,
            icon=icon,
            colors=colors,
            text_color=text_color,
            is_private=is_private,
            recipients=recipients,
            auto_compress=True
        )
        return jsonify({"ok": True, "moment": result})
    except LocketError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi đăng moment: {e}"}), 500
    finally:
        for path in temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


@app.route("/api/feed", methods=["GET"])
def api_feed():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    try:
        items = client.moments.get_latest()
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/react", methods=["POST"])
def api_react():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    moment_uid = data.get("moment_uid")
    reaction = data.get("reaction") or "❤️"
    if not moment_uid:
        return jsonify({"ok": False, "error": "Thiếu moment_uid."}), 400
    try:
        res = client.moments.react(moment_uid=moment_uid, reaction=reaction)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
