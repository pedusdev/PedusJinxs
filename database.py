import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "pedusjinxs.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # ── Tabla usuarios ────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            avatar      TEXT DEFAULT '🎮',
            bio         TEXT DEFAULT 'Sin bio todavía...',
            coins       INTEGER DEFAULT 100,
            level       INTEGER DEFAULT 1,
            xp          INTEGER DEFAULT 0,
            plan        TEXT DEFAULT 'free',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen   TEXT DEFAULT CURRENT_TIMESTAMP,
            is_online   INTEGER DEFAULT 0
        )
    """)

    # ── Tabla amigos ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            friend_id   INTEGER NOT NULL,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)   REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id),
            UNIQUE(user_id, friend_id)
        )
    """)

    # ── Tabla estadísticas de juego ───────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            game_filename   TEXT NOT NULL,
            game_name       TEXT NOT NULL,
            system          TEXT NOT NULL,
            total_time      INTEGER DEFAULT 0,
            last_played     TEXT DEFAULT CURRENT_TIMESTAMP,
            times_played    INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, game_filename)
        )
    """)

    # ── Tabla actividad ───────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            type        TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── Tabla logros ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            title       TEXT NOT NULL,
            description TEXT NOT NULL,
            icon        TEXT NOT NULL,
            earned_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente")


# ── Funciones de Usuario ─────────────────────────────

def create_user(username, email, password_hash):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO users (username, email, password)
            VALUES (?, ?, ?)
        """, (username, email, password_hash))
        conn.commit()

        # Logro de bienvenida automático
        user = get_user_by_username(username)
        add_achievement(user["id"], "¡Bienvenido!", "Te uniste a PedusJinxs", "🎉")
        add_activity(user["id"], "join", "¡Se unió a PedusJinxs!")
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_user_by_username(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


def update_user(user_id, **kwargs):
    conn = get_db()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    conn.execute(f"UPDATE users SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def set_online(user_id, online=True):
    conn = get_db()
    conn.execute("""
        UPDATE users SET is_online = ?, last_seen = ?
        WHERE id = ?
    """, (1 if online else 0, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def search_users(query, current_user_id):
    conn = get_db()
    users = conn.execute("""
        SELECT id, username, avatar, level, plan, is_online
        FROM users
        WHERE username LIKE ? AND id != ?
        LIMIT 20
    """, (f"%{query}%", current_user_id)).fetchall()
    conn.close()
    return users


# ── Funciones de Amigos ──────────────────────────────

def send_friend_request(user_id, friend_id):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO friends (user_id, friend_id, status)
            VALUES (?, ?, 'pending')
        """, (user_id, friend_id))
        conn.commit()

        # Actividad
        sender = get_user_by_id(user_id)
        add_activity(friend_id, "friend_request",
                     f"{sender['username']} te envió una solicitud de amistad")
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def accept_friend_request(user_id, friend_id):
    conn = get_db()
    conn.execute("""
        UPDATE friends SET status = 'accepted'
        WHERE user_id = ? AND friend_id = ?
    """, (friend_id, user_id))

    # Crear relación inversa
    try:
        conn.execute("""
            INSERT INTO friends (user_id, friend_id, status)
            VALUES (?, ?, 'accepted')
        """, (user_id, friend_id))
    except sqlite3.IntegrityError:
        conn.execute("""
            UPDATE friends SET status = 'accepted'
            WHERE user_id = ? AND friend_id = ?
        """, (user_id, friend_id))

    conn.commit()
    conn.close()

    # Actividad
    accepter = get_user_by_id(user_id)
    add_activity(friend_id, "friend_accept",
                 f"¡{accepter['username']} aceptó tu solicitud de amistad! 🎉")


def reject_friend_request(user_id, friend_id):
    conn = get_db()
    conn.execute("""
        DELETE FROM friends
        WHERE user_id = ? AND friend_id = ?
    """, (friend_id, user_id))
    conn.commit()
    conn.close()


def remove_friend(user_id, friend_id):
    conn = get_db()
    conn.execute("""
        DELETE FROM friends
        WHERE (user_id = ? AND friend_id = ?)
           OR (user_id = ? AND friend_id = ?)
    """, (user_id, friend_id, friend_id, user_id))
    conn.commit()
    conn.close()


def get_friends(user_id):
    conn = get_db()
    friends = conn.execute("""
        SELECT u.id, u.username, u.avatar, u.level,
               u.plan, u.is_online, u.last_seen, f.created_at
        FROM friends f
        JOIN users u ON u.id = f.friend_id
        WHERE f.user_id = ? AND f.status = 'accepted'
        ORDER BY u.is_online DESC, u.username ASC
    """, (user_id,)).fetchall()
    conn.close()
    return friends


def get_pending_requests(user_id):
    conn = get_db()
    requests = conn.execute("""
        SELECT u.id, u.username, u.avatar, u.level, f.created_at
        FROM friends f
        JOIN users u ON u.id = f.user_id
        WHERE f.friend_id = ? AND f.status = 'pending'
        ORDER BY f.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return requests


def get_friendship_status(user_id, other_id):
    conn = get_db()
    row = conn.execute("""
        SELECT status FROM friends
        WHERE (user_id = ? AND friend_id = ?)
           OR (user_id = ? AND friend_id = ?)
        LIMIT 1
    """, (user_id, other_id, other_id, user_id)).fetchone()
    conn.close()
    if not row:
        return "none"
    return row["status"]


# ── Funciones de Estadísticas ────────────────────────

def log_game_play(user_id, filename, game_name, system):
    conn = get_db()
    existing = conn.execute("""
        SELECT id, times_played FROM game_stats
        WHERE user_id = ? AND game_filename = ?
    """, (user_id, filename)).fetchone()

    if existing:
        conn.execute("""
            UPDATE game_stats
            SET times_played = times_played + 1,
                last_played = CURRENT_TIMESTAMP
            WHERE user_id = ? AND game_filename = ?
        """, (user_id, filename))
    else:
        conn.execute("""
            INSERT INTO game_stats (user_id, game_filename, game_name, system)
            VALUES (?, ?, ?, ?)
        """, (user_id, filename, game_name, system))

    # XP por jugar
    conn.execute("""
        UPDATE users SET xp = xp + 10 WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()
    check_level_up(user_id)


def get_user_stats(user_id):
    conn = get_db()
    stats = conn.execute("""
        SELECT COUNT(*) as games_played,
               SUM(times_played) as total_sessions,
               SUM(total_time) as total_time
        FROM game_stats WHERE user_id = ?
    """, (user_id,)).fetchone()

    recent = conn.execute("""
        SELECT * FROM game_stats
        WHERE user_id = ?
        ORDER BY last_played DESC LIMIT 5
    """, (user_id,)).fetchall()

    conn.close()
    return stats, recent


# ── Funciones de Logros ──────────────────────────────

def add_achievement(user_id, title, description, icon):
    conn = get_db()
    conn.execute("""
        INSERT INTO achievements (user_id, title, description, icon)
        VALUES (?, ?, ?, ?)
    """, (user_id, title, description, icon))
    conn.commit()
    conn.close()


def get_achievements(user_id):
    conn = get_db()
    achievements = conn.execute("""
        SELECT * FROM achievements
        WHERE user_id = ?
        ORDER BY earned_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return achievements


# ── Funciones de Actividad ───────────────────────────

def add_activity(user_id, type, content):
    conn = get_db()
    conn.execute("""
        INSERT INTO activity (user_id, type, content)
        VALUES (?, ?, ?)
    """, (user_id, type, content))
    conn.commit()
    conn.close()


def get_activity(user_id, limit=10):
    conn = get_db()
    activity = conn.execute("""
        SELECT * FROM activity
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return activity


def get_friends_activity(user_id, limit=20):
    conn = get_db()
    activity = conn.execute("""
        SELECT a.*, u.username, u.avatar
        FROM activity a
        JOIN users u ON u.id = a.user_id
        WHERE a.user_id IN (
            SELECT friend_id FROM friends
            WHERE user_id = ? AND status = 'accepted'
        )
        ORDER BY a.created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return activity


# ── Sistema de Niveles ───────────────────────────────

def check_level_up(user_id):
    conn = get_db()
    user = conn.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return

    xp_needed = user["level"] * 100
    if user["xp"] >= xp_needed:
        new_level = user["level"] + 1
        conn.execute("""
            UPDATE users SET level = ?, xp = xp - ?
            WHERE id = ?
        """, (new_level, xp_needed, user_id))
        conn.commit()
        add_achievement(user_id, f"¡Nivel {new_level}!",
                       f"Subiste al nivel {new_level}", "⭐")
        add_activity(user_id, "levelup", f"¡Subió al nivel {new_level}! ⭐")
    conn.close()


def get_level_title(level):
    titles = {
        1: "Novato Retro",
        2: "Jugador Casual",
        3: "Gamer Retro",
        4: "Arcade Master",
        5: "Pixel Warrior",
        6: "Console Hunter",
        7: "ROM Collector",
        8: "Retro Legend",
        9: "PedusJinxs VIP",
        10: "👑 Leyenda"
    }
    return titles.get(level, f"Nivel {level}")
