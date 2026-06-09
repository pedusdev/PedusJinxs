import os
import json
import hashlib
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, send_from_directory, jsonify,
                   flash, session)
import database as db

app = Flask(__name__)
app.secret_key = "pedus_jinxs_ultra_secret_2024"

ROMS_FOLDER = os.path.join(os.path.dirname(__file__), "roms")
os.makedirs(ROMS_FOLDER, exist_ok=True)

# Inicializar DB al arrancar
db.init_db()

# ── Sistema de consolas ──────────────────────────────
SYSTEM_MAP = {
    ".nes":  {"core": "nes",      "name": "Nintendo NES",          "icon": "🎮"},
    ".sfc":  {"core": "snes",     "name": "Super Nintendo (SNES)", "icon": "🕹️"},
    ".smc":  {"core": "snes",     "name": "Super Nintendo (SNES)", "icon": "🕹️"},
    ".gba":  {"core": "gba",      "name": "Game Boy Advance",      "icon": "🎯"},
    ".gbc":  {"core": "gbc",      "name": "Game Boy Color",        "icon": "🟢"},
    ".gb":   {"core": "gb",       "name": "Game Boy",              "icon": "⬜"},
    ".n64":  {"core": "n64",      "name": "Nintendo 64",           "icon": "🔴"},
    ".z64":  {"core": "n64",      "name": "Nintendo 64",           "icon": "🔴"},
    ".v64":  {"core": "n64",      "name": "Nintendo 64",           "icon": "🔴"},
    ".nds":  {"core": "nds",      "name": "Nintendo DS",           "icon": "📱"},
    ".md":   {"core": "segaMD",   "name": "Sega Mega Drive",       "icon": "🔵"},
    ".gen":  {"core": "segaMD",   "name": "Sega Mega Drive",       "icon": "🔵"},
    ".sms":  {"core": "segaMS",   "name": "Sega Master System",    "icon": "⚫"},
    ".gg":   {"core": "segaGG",   "name": "Sega Game Gear",        "icon": "🎲"},
    ".32x":  {"core": "sega32x",  "name": "Sega 32X",              "icon": "🔶"},
    ".pce":  {"core": "pce",      "name": "PC Engine",             "icon": "🟠"},
    ".bin":  {"core": "psx",      "name": "PlayStation 1",         "icon": "🔲"},
    ".iso":  {"core": "psx",      "name": "PlayStation 1",         "icon": "🔲"},
    ".a26":  {"core": "atari2600","name": "Atari 2600",            "icon": "🟡"},
    ".vb":   {"core": "vb",       "name": "Virtual Boy",           "icon": "🔴"},
    ".ws":   {"core": "ws",       "name": "WonderSwan",            "icon": "🟣"},
    ".wsc":  {"core": "wsc",      "name": "WonderSwan Color",      "icon": "🟣"},
    ".ngp":  {"core": "ngp",      "name": "Neo Geo Pocket",        "icon": "⚪"},
    ".ngc":  {"core": "ngpc",     "name": "Neo Geo Pocket Color",  "icon": "⚪"},
    ".tap":  {"core": "fuse",     "name": "ZX Spectrum",           "icon": "🖥️"},
    ".tzx":  {"core": "fuse",     "name": "ZX Spectrum",           "icon": "🖥️"},
    ".z80":  {"core": "fuse",     "name": "ZX Spectrum",           "icon": "🖥️"},
    ".sna":  {"core": "fuse",     "name": "ZX Spectrum",           "icon": "🖥️"},
}

ALLOWED_EXTENSIONS = set(SYSTEM_MAP.keys())


# ── Helpers ──────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_system_info(filename):
    ext = os.path.splitext(filename)[1].lower()
    return SYSTEM_MAP.get(ext, {"core": "unknown", "name": "Unknown", "icon": "❓"})


def get_all_roms():
    roms = []
    for filename in sorted(os.listdir(ROMS_FOLDER)):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            info = get_system_info(filename)
            roms.append({
                "filename": filename,
                "title": os.path.splitext(filename)[0].replace("_", " ").replace("-", " "),
                "system": info["name"],
                "core": info["core"],
                "icon": info["icon"],
                "size": round(os.path.getsize(os.path.join(ROMS_FOLDER, filename)) / 1024, 1)
            })
    return roms


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("⚠️ Debes iniciar sesión primero.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if "user_id" in session:
        return db.get_user_by_id(session["user_id"])
    return None


# ── Contexto global ──────────────────────────────────
@app.context_processor
def inject_user():
    user = get_current_user()
    pending_count = 0
    if user:
        pending_count = len(db.get_pending_requests(user["id"]))
    return dict(
        current_user=user,
        pending_requests_count=pending_count,
        get_level_title=db.get_level_title
    )


# ── Auth Routes ──────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)
        if user and user["password"] == hash_password(password):
            session["user_id"] = user["id"]
            db.set_online(user["id"], True)
            db.add_activity(user["id"], "login", "Inició sesión 🟢")
            flash(f"¡Bienvenido de vuelta, {username}! 🎮", "success")
            return redirect(url_for("index"))
        else:
            flash("❌ Usuario o contraseña incorrectos.", "error")

    return render_template("auth/login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if len(username) < 3:
            flash("❌ El usuario debe tener al menos 3 caracteres.", "error")
        elif len(password) < 6:
            flash("❌ La contraseña debe tener al menos 6 caracteres.", "error")
        elif password != confirm:
            flash("❌ Las contraseñas no coinciden.", "error")
        elif db.get_user_by_username(username):
            flash("❌ Ese nombre de usuario ya existe.", "error")
        elif db.get_user_by_email(email):
            flash("❌ Ese email ya está registrado.", "error")
        else:
            if db.create_user(username, email, hash_password(password)):
                user = db.get_user_by_username(username)
                session["user_id"] = user["id"]
                db.set_online(user["id"], True)
                flash(f"¡Bienvenido a PedusJinxs, {username}! 🎉", "success")
                return redirect(url_for("index"))

    return render_template("auth/register.html")


@app.route("/logout")
def logout():
    if "user_id" in session:
        db.set_online(session["user_id"], False)
    session.clear()
    flash("👋 Sesión cerrada.", "success")
    return redirect(url_for("login"))


# ── Profile Routes ───────────────────────────────────

@app.route("/profile")
@app.route("/profile/<username>")
@login_required
def profile(username=None):
    if username is None:
        user = get_current_user()
        is_own = True
    else:
        user = db.get_user_by_username(username)
        if not user:
            flash("❌ Usuario no encontrado.", "error")
            return redirect(url_for("index"))
        is_own = (user["id"] == session["user_id"])

    stats, recent_games = db.get_user_stats(user["id"])
    achievements = db.get_achievements(user["id"])
    activity = db.get_activity(user["id"], 8)
    friends = db.get_friends(user["id"])
    friendship = None if is_own else db.get_friendship_status(session["user_id"], user["id"])
    xp_needed = user["level"] * 100
    xp_percent = int((user["xp"] / xp_needed) * 100) if xp_needed > 0 else 0

    return render_template("profile.html",
        user=user,
        is_own=is_own,
        stats=stats,
        recent_games=recent_games,
        achievements=achievements,
        activity=activity,
        friends=friends,
        friendship=friendship,
        xp_needed=xp_needed,
        xp_percent=xp_percent
    )


@app.route("/profile/edit", methods=["POST"])
@login_required
def edit_profile():
    user_id = session["user_id"]
    bio    = request.form.get("bio", "").strip()[:150]
    avatar = request.form.get("avatar", "🎮")

    db.update_user(user_id, bio=bio, avatar=avatar)
    flash("✅ Perfil actualizado.", "success")
    return redirect(url_for("profile"))


# ── Friends Routes ───────────────────────────────────

@app.route("/friends")
@login_required
def friends():
    user_id  = session["user_id"]
    friends  = db.get_friends(user_id)
    pending  = db.get_pending_requests(user_id)
    feed     = db.get_friends_activity(user_id, 20)
    query    = request.args.get("search", "").strip()
    results  = db.search_users(query, user_id) if query else []

    return render_template("friends.html",
        friends=friends,
        pending=pending,
        feed=feed,
        results=results,
        query=query
    )


@app.route("/friends/add/<int:friend_id>", methods=["POST"])
@login_required
def add_friend(friend_id):
    db.send_friend_request(session["user_id"], friend_id)
    flash("✅ Solicitud de amistad enviada.", "success")
    return redirect(request.referrer or url_for("friends"))


@app.route("/friends/accept/<int:friend_id>", methods=["POST"])
@login_required
def accept_friend(friend_id):
    db.accept_friend_request(session["user_id"], friend_id)
    friend = db.get_user_by_id(friend_id)
    flash(f"🎉 ¡Ahora eres amigo de {friend['username']}!", "success")
    return redirect(url_for("friends"))


@app.route("/friends/reject/<int:friend_id>", methods=["POST"])
@login_required
def reject_friend(friend_id):
    db.reject_friend_request(session["user_id"], friend_id)
    flash("❌ Solicitud rechazada.", "success")
    return redirect(url_for("friends"))


@app.route("/friends/remove/<int:friend_id>", methods=["POST"])
@login_required
def remove_friend(friend_id):
    db.remove_friend(session["user_id"], friend_id)
    flash("🗑️ Amigo eliminado.", "success")
    return redirect(url_for("friends"))


# ── Game Routes ──────────────────────────────────────

@app.route("/")
def index():
    roms    = get_all_roms()
    systems = sorted(set(r["system"] for r in roms))
    return render_template("index.html", roms=roms, systems=systems)


@app.route("/play/<filename>")
def play(filename):
    filepath = os.path.join(ROMS_FOLDER, filename)
    if not os.path.exists(filepath):
        flash("❌ ROM no encontrada.", "error")
        return redirect(url_for("index"))
    info  = get_system_info(filename)
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")

    # Log stats si hay sesión activa
    if "user_id" in session:
        db.log_game_play(session["user_id"], filename, title, info["name"])
        db.add_activity(session["user_id"], "play",
                       f"Está jugando {title} ({info['name']}) 🎮")

    return render_template("play.html",
        filename=filename, title=title,
        system=info["name"], core=info["core"], icon=info["icon"]
    )


@app.route("/roms/<filename>")
def serve_rom(filename):
    return send_from_directory(ROMS_FOLDER, filename)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "rom" not in request.files:
        flash("❌ No se seleccionó ningún archivo.", "error")
        return redirect(url_for("index"))

    file = request.files["rom"]
    if file.filename == "":
        flash("❌ Nombre vacío.", "error")
        return redirect(url_for("index"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash(f"❌ Extensión '{ext}' no soportada.", "error")
        return redirect(url_for("index"))

    file.save(os.path.join(ROMS_FOLDER, file.filename))
    db.add_activity(session["user_id"], "upload",
                   f"Subió {file.filename} a la biblioteca 📤")
    flash(f"✅ '{file.filename}' subido exitosamente.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<filename>", methods=["POST"])
@login_required
def delete_rom(filename):
    filepath = os.path.join(ROMS_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"🗑️ '{filename}' eliminado.", "success")
    else:
        flash("❌ ROM no encontrada.", "error")
    return redirect(url_for("index"))


@app.route("/store")
def store():
    return render_template("store.html")


@app.route("/api/roms")
def api_roms():
    return jsonify(get_all_roms())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
