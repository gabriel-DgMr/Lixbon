import hashlib
import secrets
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("app/data.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    # Hash simple con sha256 (idealmente usar bcrypt, pero nos mantenemos con librerias estandar)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                model TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT,
                client_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );
            """
        )
        try:
            conn.execute("ALTER TABLE api_keys ADD COLUMN raw_key TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE api_keys ADD COLUMN model TEXT;")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def create_user(username: str, password: str) -> dict[str, Any] | None:
    try:
        pw_hash = hash_password(password)
        created_at = now_iso()
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, pw_hash, created_at),
            )
            user_id = cur.lastrowid
            conn.commit()
            return {"id": user_id, "username": username}
    except sqlite3.IntegrityError:
        return None # Usuario ya existe


def verify_user(username: str, password: str) -> dict[str, Any] | None:
    pw_hash = hash_password(password)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
            (username, pw_hash)
        ).fetchone()
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    return None

def create_api_key(name: str, user_id: int, model: str | None = None) -> tuple[str, dict[str, Any]]:
    raw_key = f"lan_{secrets.token_urlsafe(24)}"
    key_hash = hash_api_key(raw_key)
    created_at = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO api_keys(user_id, name, key_hash, raw_key, created_at, active, model) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (user_id, name, key_hash, raw_key, created_at, model),
        )
        conn.commit()
        key_data = {
            "id": cur.lastrowid,
            "name": name,
            "model": model,
            "active": True,
            "created_at": created_at,
        }
    return raw_key, key_data


def list_api_keys(user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                "SELECT id, name, key_hash, raw_key, created_at, active, model FROM api_keys WHERE user_id = ? ORDER BY id DESC",
                (user_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, key_hash, raw_key, created_at, active, model FROM api_keys ORDER BY id DESC"
            ).fetchall()

    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "model": row["model"],
                "masked_key": f"lan_...{row['key_hash'][-6:]}",
                "raw_key": row["raw_key"],
                "active": bool(row["active"]),
                "created_at": row["created_at"],
            }
        )
    return result


def validate_api_key(raw_key: str) -> dict[str, Any] | None:
    """Devuelve los datos del usuario (y modelo vinculado) si la key es valida."""
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, model FROM api_keys WHERE key_hash = ? AND active = 1", (key_hash,)
        ).fetchone()

    if row:
        user = get_user_by_id(row["user_id"])
        if user:
            # Adjunta el modelo vinculado a la key (None = global, sin restriccion)
            user["key_model"] = row["model"]
        return user
    return None


def ensure_conversation(conversation_id: str, user_id: int, title: str | None, client_id: str | None) -> None:
    ts = now_iso()
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE conversations SET updated_at = ?, title = COALESCE(?, title), client_id = COALESCE(?, client_id) WHERE id = ?",
                (ts, title, client_id, conversation_id),
            )
        else:
            conn.execute(
                "INSERT INTO conversations(id, user_id, title, client_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, user_id, title, client_id, ts, ts),
            )
        conn.commit()


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    model: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
) -> None:
    total_tokens = prompt_tokens + completion_tokens
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO messages(
                conversation_id, role, content, model, prompt_tokens,
                completion_tokens, total_tokens, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                now_iso(),
            ),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now_iso(), conversation_id),
        )
        conn.commit()


def get_usage_summary(user_id: int | None = None) -> dict[str, int]:
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT c.id) AS conversations,
                    COUNT(m.id) AS messages,
                    COALESCE(SUM(m.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(m.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(m.total_tokens), 0) AS total_tokens
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                """, (user_id,)
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT c.id) AS conversations,
                    COUNT(m.id) AS messages,
                    COALESCE(SUM(m.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(m.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(m.total_tokens), 0) AS total_tokens
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                """
            ).fetchone()
            
    return dict(row) if row else {
        "conversations": 0,
        "messages": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def list_recent_conversations(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT id, COALESCE(title, 'Sin titulo') AS title, client_id, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, COALESCE(title, 'Sin titulo') AS title, client_id, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def list_clients_usage(limit: int = 50, user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(c.client_id, 'sin_client_id') AS client_id,
                    COUNT(DISTINCT c.id) AS conversations,
                    COUNT(m.id) AS messages,
                    COALESCE(SUM(m.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(m.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(m.total_tokens), 0) AS total_tokens,
                    MAX(c.updated_at) AS last_activity
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                GROUP BY COALESCE(c.client_id, 'sin_client_id')
                ORDER BY last_activity DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(c.client_id, 'sin_client_id') AS client_id,
                    COUNT(DISTINCT c.id) AS conversations,
                    COUNT(m.id) AS messages,
                    COALESCE(SUM(m.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(m.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(m.total_tokens), 0) AS total_tokens,
                    MAX(c.updated_at) AS last_activity
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY COALESCE(c.client_id, 'sin_client_id')
                ORDER BY last_activity DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]
