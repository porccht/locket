import os
import json
import time
import tempfile
from flask import Flask, request, jsonify, render_template
from locketlam import LocketClient, NoteType
from locketlam.exceptions import LocketError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "locketlam_session.json")
PRESETS_FILE = os.path.join(BASE_DIR, "locketlam", "caption_presets.json")
CUSTOM_META_FILE = os.path.join(BASE_DIR, "user_custom_meta.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024

client = LocketClient(session_path=SESSION_FILE)

DEFAULT_META = {
    "birthday": "Tháng 5 16th",
    "email_display": "",
    "gold_badge": True,
    "frame_style": "frame-rgb-liquid",
    "about_lines": [
        "Thanh Long ❤️‍🩹: Facebook.com/htl165",
        "Thanh Long ❤️‍🩹: Tiktok.com/@tlongmmo",
    ],
}

QUICK_CAPTIONS = [
    {"id": "standard", "label": "Văn bản", "icon": "Aa", "colors": [], "text_color": "#FFFFFF"},
    {"id": NoteType.REVIEW, "label": "Review", "icon": "⭐", "colors": ["#2B2A24", "#3B382A"], "text_color": "#FFD43B"},
    {"id": NoteType.LOCATION, "label": "Location", "icon": "📍", "colors": ["#1E252B", "#2C3842"], "text_color": "#FFFFFF"},
    {"id": NoteType.WEATHER, "label": "Weather", "icon": "☁️", "colors": ["#4A6FA5", "#7790A6"], "text_color": "#FFFFFF"},
    {"id": NoteType.TIME, "label": "13:22", "icon": "🕒", "colors": ["#22252A", "#32363E"], "text_color": "#FFFFFF"},
    {"id": NoteType.STREAK, "label": "1", "icon": "🔥", "colors": ["#3A2416", "#5E3519"], "text_color": "#FF9F1C"},
    {"id": NoteType.PARTY_TIME, "label": "Party Time!", "icon": "🪩", "colors": ["#1EA866", "#2BD984"], "text_color": "#FFFFFF"},
    {"id": NoteType.OOTD, "label": "OOTD", "icon": "🕶", "colors": ["#1F2224", "#35393C"], "text_color": "#FFFFFF"},
    {"id": NoteType.MISS_YOU, "label": "Miss you", "icon": "🥰", "colors": ["#E62E4D", "#FF5E7E"], "text_color": "#FFFFFF"},
    {"id": NoteType.DANG_BAN_TUONG_TU, "label": "Đang bận tương tư", "icon": "💭", "colors": ["#FF758C", "#FF7EB3"], "text_color": "#FFFFFF"},
    {"id": NoteType.DOI_ROI, "label": "Dỗi rồi", "icon": "😤", "colors": ["#FF416C", "#FF4B2B"], "text_color": "#FFFFFF"},
    {"id": NoteType.MUON_DUOC_OM, "label": "Muốn được ôm", "icon": "🫂", "colors": ["#667EEA", "#764BA2"], "text_color": "#FFFFFF"},
]


def with_cache_bust(url: str) -> str:
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}cb={int(time.time())}"


def load_meta() -> dict:
    data = dict(DEFAULT_META)
    if os.path.exists(CUSTOM_META_FILE):
        try:
            with open(CUSTOM_META_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    data.update(saved)
        except Exception:
            pass
    return data


def save_meta(new_data: dict) -> dict:
    current = load_meta()
    current.update(new_data)
    try:
        with open(CUSTOM_META_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return current


def load_presets() -> list:
    items = list(QUICK_CAPTIONS)
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            seen = {x["id"] for x in items}
            for k, v in raw.items():
                if not isinstance(v, dict):
                    continue
                oid = (v.get("overlay_id") or k).replace("caption:", "")
                if oid in seen or k in seen:
                    continue
                seen.add(oid)
                items.append({
                    "id": oid,
                    "label": v.get("text") or k.replace("_", " ").title(),
                    "icon": v.get("icon") or "",
                    "colors": v.get("colors") or [],
                    "text_color": v.get("text_color") or "#FFFFFF",
                })
                if len(items) >= 32:
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
    profile = {}
    friends = []
    meta = load_meta()

    if authed:
        try:
            p = client.user.get_profile()
            if isinstance(p, dict):
                profile = p
        except Exception:
            profile = {}
        try:
            raw_f = client.friends.get_all_friends() or []
            for item in raw_f:
                if isinstance(item, dict):
                    uid = item.get("uid") or item.get("id") or ""
                    fn = item.get("first_name") or item.get("firstName") or ""
                    ln = item.get("last_name") or item.get("lastName") or ""
                    full = f"{fn} {ln}".strip() or item.get("username") or uid[:8]
                    av = item.get("profile_picture_url") or item.get("profile_pic") or item.get("avatar_url") or item.get("photo_url") or ""
                    if uid:
                        friends.append({"uid": uid, "name": full, "avatar": av})
        except Exception:
            friends = []

    uid = client.session.uid if authed else ""
    username = profile.get("username") or (uid[:10] if uid else "tlong")
    raw_avatar = profile.get("profile_picture_url") or profile.get("profile_pic") or profile.get("avatar_url") or ""
    return jsonify({
        "authenticated": authed,
        "uid": uid,
        "invite_link": f"https://locket.cam/{username}",
        "profile": {
            "first_name": profile.get("first_name") or "Thanh Long",
            "last_name": profile.get("last_name") or "❤️‍🩹",
            "username": username,
            "email": meta.get("email_display") or profile.get("email") or "",
            "birthdate": profile.get("birthdate") or meta.get("birthday") or "Tháng 5 16th",
            "avatar": with_cache_bust(raw_avatar) if raw_avatar else "",
        },
        "meta": meta,
        "friends": friends,
        "presets": load_presets(),
    })


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or data.get("email") or data.get("phone") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"ok": False, "error": "Vui lòng nhập đầy đủ Email/SĐT và Mật khẩu."}), 400
    try:
        client.login(identifier, password)
        return jsonify({"ok": True, "uid": client.session.uid})
    except LocketError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    try:
        if hasattr(client.session, "logout"):
            client.session.logout()
        else:
            client.session.id_token = None
            client.session.uid = None
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/profile/update", methods=["POST"])
def api_profile_update():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email_val = (data.get("email") or "").strip()
    birthday_val = (data.get("birthday") or "").strip()
    gold_badge = data.get("gold_badge")
    frame_style = data.get("frame_style")

    try:
        if first_name or last_name:
            client.user.update_name(first_name=first_name or "Thanh Long", last_name=last_name or "")
        if birthday_val and hasattr(client.user, "update_birthdate"):
            try:
                client.user.update_birthdate(birthday_val)
            except Exception:
                pass
        meta_patch = {}
        if email_val:
            meta_patch["email_display"] = email_val
        if birthday_val:
            meta_patch["birthday"] = birthday_val
        if isinstance(gold_badge, bool):
            meta_patch["gold_badge"] = gold_badge
        if frame_style:
            meta_patch["frame_style"] = frame_style
        saved = save_meta(meta_patch)
        return jsonify({"ok": True, "meta": saved})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/profile/avatar", methods=["POST"])
def api_profile_avatar():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    file = request.files.get("avatar")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Chưa chọn ảnh đại diện."}), 400
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        file.save(tmp_path)
        uploaded_url = client.user.update_avatar(tmp_path)
        fresh_profile = {}
        try:
            fresh_profile = client.user.get_profile() or {}
        except Exception:
            fresh_profile = {}
        final_url = (
            fresh_profile.get("profile_picture_url")
            or fresh_profile.get("profile_pic")
            or fresh_profile.get("avatar_url")
            or (uploaded_url if isinstance(uploaded_url, str) else "")
        )
        return jsonify({
            "ok": True,
            "avatar_url": with_cache_bust(final_url) if final_url else ""
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.route("/api/post", methods=["POST"])
def api_post():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Vui lòng đăng nhập trước khi gửi."}), 401

    temp_files = []
    try:
        caption = (request.form.get("caption") or "").strip()
        preset_id = (request.form.get("preset_id") or "standard").strip()
        icon = (request.form.get("icon") or "").strip() or None
        colors_raw = (request.form.get("colors") or "").strip()
        text_color = (request.form.get("text_color") or "").strip() or None
        audience = (request.form.get("audience") or "all").strip()
        recipients_raw = (request.form.get("recipients") or "").strip()
        priority = (request.form.get("priority") or "balanced").strip()

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
            return jsonify({"ok": False, "error": "Chụp ảnh, quay video hoặc chọn từ thư viện trước khi gửi."}), 400

        res = client.moments.post(
            image=image_input,
            video=video_input,
            caption=caption,
            note_type=preset_id,
            icon=icon,
            colors=colors,
            text_color=text_color,
            is_private=is_private,
            recipients=recipients,
            auto_compress=True,
            priority=priority,
        )
        return jsonify({"ok": True, "moment": res})
    except LocketError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
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
    mid = data.get("moment_uid")
    emo = data.get("reaction") or "💛"
    if not mid:
        return jsonify({"ok": False, "error": "Thiếu moment_uid."}), 400
    try:
        res = client.moments.react(moment_uid=mid, reaction=emo)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/comment", methods=["POST"])
def api_comment():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    mid = data.get("moment_uid")
    uid = data.get("receiver_uid")
    text = (data.get("text") or "").strip()
    if not mid or not uid or not text:
        return jsonify({"ok": False, "error": "Thiếu nội dung tin nhắn."}), 400
    try:
        res = client.moments.comment(moment_uid=mid, receiver_uid=uid, text=text)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/chat/send", methods=["POST"])
def api_chat_send():
    if not client.is_authenticated():
        return jsonify({"ok": False, "error": "Chưa đăng nhập."}), 401
    data = request.get_json(silent=True) or {}
    uid = (data.get("receiver_uid") or "").strip()
    text = (data.get("text") or "").strip()
    if not uid or not text:
        return jsonify({"ok": False, "error": "Thiếu người nhận hoặc tin nhắn."}), 400
    try:
        res = client.chat.send_message(receiver_uid=uid, text=text)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
