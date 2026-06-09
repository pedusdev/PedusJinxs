import os
import json
import mimetypes
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash

# 👇 AÑADE ESTAS 3 LÍNEAS
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/html', '.html')

app = Flask(__name__)
app.secret_key = "pedus_jinxs_secret_2024"

ROMS_FOLDER = os.path.join(os.path.dirname(__file__), "roms")
os.makedirs(ROMS_FOLDER, exist_ok=True)

# ─── Mapeo de extensión → core de EmulatorJS ────────────────────────────────
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
}

ALLOWED_EXTENSIONS = set(SYSTEM_MAP.keys())


def get_system_info(filename):
    """Retorna info del sistema según la extensión del archivo."""
    ext = os.path.splitext(filename)[1].lower()
    return SYSTEM_MAP.get(ext, {"core": "unknown", "name": "Unknown System", "icon": "❓"})


def get_all_roms():
    """Lista todos los ROMs en la carpeta /roms."""
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


# ─── Rutas ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    roms = get_all_roms()
    systems = sorted(set(r["system"] for r in roms))
    return render_template("index.html", roms=roms, systems=systems)


@app.route("/play/<filename>")
def play(filename):
    filepath = os.path.join(ROMS_FOLDER, filename)
    if not os.path.exists(filepath):
        flash("❌ ROM no encontrada.", "error")
        return redirect(url_for("index"))
    info = get_system_info(filename)
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
    return render_template("play.html",
                           filename=filename,
                           title=title,
                           system=info["name"],
                           core=info["core"],
                           icon=info["icon"])


@app.route("/roms/<filename>")
def serve_rom(filename):
    """Sirve el archivo ROM al navegador."""
    return send_from_directory(ROMS_FOLDER, filename)


@app.route("/upload", methods=["POST"])
def upload():
    if "rom" not in request.files:
        flash("❌ No se seleccionó ningún archivo.", "error")
        return redirect(url_for("index"))

    file = request.files["rom"]
    if file.filename == "":
        flash("❌ Nombre de archivo vacío.", "error")
        return redirect(url_for("index"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash(f"❌ Extensión '{ext}' no soportada.", "error")
        return redirect(url_for("index"))

    save_path = os.path.join(ROMS_FOLDER, file.filename)
    file.save(save_path)
    flash(f"✅ '{file.filename}' subido exitosamente.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<filename>", methods=["POST"])
def delete_rom(filename):
    filepath = os.path.join(ROMS_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"🗑️ '{filename}' eliminado.", "success")
    else:
        flash("❌ ROM no encontrada.", "error")
    return redirect(url_for("index"))


@app.route("/api/roms")
def api_roms():
    """API JSON para listar ROMs."""
    return jsonify(get_all_roms())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)