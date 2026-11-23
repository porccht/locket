import os
import json
import tempfile
from flask import Flask, request, jsonify, render_template
from locketlam import LocketClient, NoteType
from locketlam.exceptions import LocketError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "locketlam_session.json")
PRESETS_FILE = os.path.join(BASE_DIR, "locketlam", "caption_presets.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

client = LocketClient(session_path=SESSION_FILE)

CURATED_PRESETS = [
    {"id": "standard", "label": "Mặc định", "icon": "", "colors": [], "text_color": "#FFFFFF"},
    {"id": NoteType.DANG_BAN_TUONG_TU, "label": "Đang bận tương tư", "icon": "💭", "colors": ["#FF758C", "#FF7EB3"], "text_color": "#FFFFFF"},
    {"id": NoteType.DOI_ROI, "label": "Dỗi rồi", "icon": "😤", "colors": ["#FF416C", "#FF4B2B"], "text_color": "#FFFFFF"},
    {"id": NoteType.MUON_DUOC_OM, "label": "Muốn được ôm", "icon": "🫂", "colors": ["#667EEA", "#764BA2"], "text_color": "#FFFFFF"},
    {"id": NoteType.OOTD, "label": "OOTD", "icon": "🕶", "colors": ["#232526", "#414345"], "text_color": "#FFFFFF"},
    {"id": NoteType.NGAY_MOI_VUI_VE, "label": "Ngày mới vui vẻ", "icon": "☀️", "colors": ["#F7971E", "#FFD200"], "text_color": "#141418"},
    {"id": NoteType.NGU_NGON, "label": "Ngủ ngon", "icon": "🌙", "colors": ["#141E30", "#243B55"], "text_color": "#FFFFFF"},
]


def load_preset_catalog():
    items = list(CURATED_PRESETS)
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            existing_ids = {p["id"] for p in items}
            for key, val in raw.items():
                if not isinstance(val, dict):
                    continue
                pid = val.get("overlay_id") or key
                clean_id = pid.replace("caption:", "")
                if clean_id in existing_ids or key in existing_ids:
                    continue
                label = val.get("text") or key.replace("_", " ").title()
                items.append({
                    "id": clean_id,
                    "label": label,
                    "icon": val.get("icon") or "",
                    "colors": val.get("colors") or [],
                    "text_color": val.get("text_color") or "#FFFFFF"
                })
                if len(items) >= 36:
                    break
        except Exception:
            pass
    return items


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/boot", methods=["GET"])
def api_boot():
    authed = client.is_authenticated()
    profile = None
    friends = []
    if authed:
        try:
            profile = client.user.get_profile()
        except Exception:
            profile = None
        try:
            raw_friends = client.friends.get_all_friends() or []
            for fr in raw_friends:
                if isinstance(fr, dict):
                    uid = fr.get("uid") or fr.get("id") or ""
                    first = fr.get("first_name") or fr.get("firstName") or ""
                    last = fr.get("last_name") or fr.get("lastName") or ""
                    name = f"{first} {last}".strip() or fr.get("username") or uid[:8]
                    avatar = fr.get("profile_pic") or fr.get("avatar_url") or fr.get("photo_url") or ""
                    if uid:
                        friends.append({"uid": uid, "name": name, "avatar": avatar})
        except Exception:
            friends = []

    return jsonify({
        "authenticated": authed,
        "uid": client.session.uid if authed else None,
        "profile": profile,
        "friends": friends,
        "presets": load_preset_catalog()
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Vui lòng nhập email và mật khẩu."}), 400
    try:
        client.login(email, password)
        return jsonify({"ok": True, "uid": client.session.uid})
    except LocketError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi đăng nhập: {e}"}), 500


@app.route("/api/post", methods=["POST"])
def api_post():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Vui lòng đăng nhập trước."}), 401

    temp_files = []
    try:
        caption = (request.form.get("caption") or "").strip()
        preset_id = (request.form.get("preset_id") or "standard").strip()
        icon = (request.form.get("icon") or "").strip() or None
        colors_raw = (request.form.get("colors") or "").strip()
        text_color = (request.form.get("text_color") or "").strip() or None
        audience = (request.form.get("audience") or "all").strip()
        recipients_raw = (request.form.get("recipients") or "").strip()

        colors = [c.strip() for c in colors_raw.split(",") if c.strip()] or None
        is_private = audience == "private"
        recipients = None
        if audience == "selected" and recipients_raw:
            recipients = [u.strip() for u in recipients_raw.split(",") if u.strip()]

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

        if vid_file and vid_file.filename:
            ext = os.path.splitext(vid_file.filename)[1] or ".mp4"
            fd, tmp_vid = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            vid_file.save(tmp_vid)
            temp_files.append(tmp_vid)
            video_input = tmp_vid

        if not image_input and not video_input:
            return jsonify({"ok": False, "error": "Chụp ảnh hoặc chọn ảnh/video trước khi gửi."}), 400

        note_type = preset_id if preset_id else NoteType.STANDARD
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
        return jsonify({"ok": False, "error": f"Không thể gửi moment: {e}"}), 500
    finally:
        for p in temp_files:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@app.route("/api/feed", methods=["GET"])
def api_feed():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    try:
        items = client.moments.get_latest() or []
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/memories", methods=["GET"])
def api_memories():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    try:
        items = client.moments.get_all_my_moments(limit=36) or []
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/react", methods=["POST"])
def api_react():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    moment_uid = data.get("moment_uid")
    reaction = data.get("reaction") or "💛"
    if not moment_uid:
        return jsonify({"ok": False, "error": "Thiếu moment_uid."}), 400
    try:
        res = client.moments.react(moment_uid=moment_uid, reaction=reaction)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/comment", methods=["POST"])
def api_comment():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    moment_uid = data.get("moment_uid")
    receiver_uid = data.get("receiver_uid")
    text = (data.get("text") or "").strip()
    if not moment_uid or not receiver_uid or not text:
        return jsonify({"ok": False, "error": "Thiếu thông tin tin nhắn."}), 400
    try:
        res = client.moments.comment(moment_uid=moment_uid, receiver_uid=receiver_uid, text=text)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
