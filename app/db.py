import hashlib
import math
import secrets
import struct
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("app/data.db")
KEY_EXPIRY_DAYS = 90
INACTIVE_ARCHIVE_DAYS = 30


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ─── Helpers vectoriales (stdlib puro, sin dependencias externas) ──────────

def serialize_vector(vec: list[float]) -> bytes:
    """Serializa un vector de floats a bytes para almacenar como BLOB."""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(blob: bytes) -> tuple[float, ...]:
    """Deserializa un BLOB a tupla de floats."""
    n = len(blob) // 4
    return struct.unpack(f"{n}f", blob)


def cosine_similarity(v1: Any, v2: Any) -> float:
    """Similitud coseno entre dos vectores. Implementación pura Python."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ─── Conexión ──────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ─── Inicialización y migración de esquema ─────────────────────────────────

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
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
                key_prefix TEXT,
                raw_key TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                scopes TEXT NOT NULL DEFAULT 'read,write',
                model TEXT,
                expires_at TEXT,
                last_accessed TEXT,
                last_used_ip TEXT,
                deactivated_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            /* Los índices de api_keys se crean después de la migración */

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

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                key_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_user_type
                ON audit_events(user_id, event_type, created_at);

            CREATE TABLE IF NOT EXISTS task_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_input TEXT NOT NULL,
                intent TEXT,
                complexity REAL,
                domain TEXT,
                risk_level TEXT,
                router_used TEXT,
                model_called TEXT,
                response_summary TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                embedding_blob BLOB,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_task_emb_user
                ON task_embeddings(user_id, created_at);
        """)
        
        # Primero migramos las columnas nuevas (como is_active)
        _migrate_columns(conn)
        
        # Luego creamos los índices que dependen de esas columnas
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_user_active
                ON api_keys(user_id, is_active);
            CREATE INDEX IF NOT EXISTS idx_api_keys_composite
                ON api_keys(user_id, is_active, created_at);
        """)
        
        conn.commit()


def _migrate_columns(conn) -> None:
    """Agrega columnas a api_keys si no existen (compatible con BD preexistente)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}

    migrations = [
        ("raw_key",        "ALTER TABLE api_keys ADD COLUMN raw_key TEXT"),
        ("model",          "ALTER TABLE api_keys ADD COLUMN model TEXT"),
        ("key_prefix",     "ALTER TABLE api_keys ADD COLUMN key_prefix TEXT"),
        ("is_active",      "ALTER TABLE api_keys ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"),
        ("status",         "ALTER TABLE api_keys ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"),
        ("scopes",         "ALTER TABLE api_keys ADD COLUMN scopes TEXT NOT NULL DEFAULT 'read,write'"),
        ("expires_at",     "ALTER TABLE api_keys ADD COLUMN expires_at TEXT"),
        ("last_accessed",  "ALTER TABLE api_keys ADD COLUMN last_accessed TEXT"),
        ("last_used_ip",   "ALTER TABLE api_keys ADD COLUMN last_used_ip TEXT"),
        ("deactivated_at", "ALTER TABLE api_keys ADD COLUMN deactivated_at TEXT"),
    ]
    for col_name, sql in migrations:
        if col_name not in existing:
            try:
                conn.execute(sql)
            except Exception:
                pass

    # Sincronizar columna antigua 'active' → 'is_active'
    if "active" in existing:
        conn.execute(
            "UPDATE api_keys SET is_active = active WHERE is_active != active"
        )

    # Asignar expires_at retroactivamente (created_at + 90 días)
    conn.execute("""
        UPDATE api_keys
        SET expires_at = datetime(created_at, '+90 days')
        WHERE expires_at IS NULL
    """)

    # Asignar status retroactivamente
    conn.execute("UPDATE api_keys SET status = 'active' WHERE status IS NULL AND is_active = 1")
    conn.execute("UPDATE api_keys SET status = 'inactive' WHERE status IS NULL AND is_active = 0")

    # Asignar key_prefix retroactivamente desde raw_key
    conn.execute("""
        UPDATE api_keys
        SET key_prefix = substr(raw_key, 1, 12)
        WHERE key_prefix IS NULL AND raw_key IS NOT NULL
    """)


# ─── Usuarios ──────────────────────────────────────────────────────────────

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
        return None


def verify_user(username: str, password: str) -> dict[str, Any] | None:
    pw_hash = hash_password(password)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
            (username, pw_hash),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ─── API Keys ──────────────────────────────────────────────────────────────

def _key_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=KEY_EXPIRY_DAYS)).isoformat()


def get_active_key_for_user(user_id: int) -> dict[str, Any] | None:
    """Retorna la key activa y no expirada del usuario, si existe."""
    now = now_iso()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, raw_key, expires_at, scopes, model, key_prefix, created_at
            FROM api_keys
            WHERE user_id = ?
              AND is_active = 1
              AND status = 'active'
              AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, now),
        ).fetchone()
    return dict(row) if row else None


def create_api_key(
    name: str,
    user_id: int,
    model: str | None = None,
    scopes: str = "read,write",
) -> tuple[str, dict[str, Any]]:
    raw_key = f"lan_{secrets.token_urlsafe(24)}"
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:12]
    created_at = now_iso()
    expires_at = _key_expires_at()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO api_keys(
                user_id, name, key_hash, raw_key, key_prefix,
                is_active, status, scopes, model,
                expires_at, last_accessed, created_at
            ) VALUES (?, ?, ?, ?, ?, 1, 'active', ?, ?, ?, ?, ?)
            """,
            (user_id, name, key_hash, raw_key, key_prefix,
             scopes, model, expires_at, created_at, created_at),
        )
        conn.commit()
        key_data = {
            "id": cur.lastrowid,
            "name": name,
            "model": model,
            "scopes": scopes.split(","),
            "is_active": True,
            "status": "active",
            "key_prefix": key_prefix,
            "created_at": created_at,
            "expires_at": expires_at,
        }
    return raw_key, key_data


def deactivate_key(key_id: int) -> bool:
    """Soft delete de una key específica."""
    now = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE api_keys
            SET is_active = 0, status = 'inactive', deactivated_at = ?
            WHERE id = ?
            """,
            (now, key_id),
        )
        conn.commit()
    return True


def deactivate_all_user_keys(user_id: int) -> None:
    """Marca todas las keys activas del usuario como inactivas."""
    now = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE api_keys
            SET is_active = 0, status = 'inactive', deactivated_at = ?
            WHERE user_id = ? AND is_active = 1
            """,
            (now, user_id),
        )
        conn.commit()


def update_last_accessed(key_hash: str, ip_address: str | None) -> None:
    """Actualiza timestamp y la IP de último uso de la key."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE api_keys SET last_accessed = ?, last_used_ip = ? WHERE key_hash = ?",
            (now_iso(), ip_address, key_hash),
        )
        conn.commit()


def archive_old_inactive_keys() -> int:
    """Archiva keys inactivas con más de INACTIVE_ARCHIVE_DAYS días. Retorna el número archivadas."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=INACTIVE_ARCHIVE_DAYS)
    ).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE api_keys
            SET status = 'archived'
            WHERE status = 'inactive' AND deactivated_at < ?
            """,
            (cutoff,),
        )
        conn.commit()
    return cur.rowcount


def count_daily_regenerations(user_id: int) -> int:
    """Cuenta cuántas veces regeneró su key el usuario hoy (UTC)."""
    today_start = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE user_id = ? AND event_type = 'api_key_regenerated' AND created_at >= ?
            """,
            (user_id, today_start),
        ).fetchone()
    return row[0] if row else 0


def list_api_keys(user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT id, name, key_hash, raw_key, key_prefix, is_active,
                       status, model, scopes, expires_at, last_accessed,
                       last_used_ip, created_at
                FROM api_keys
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, key_hash, raw_key, key_prefix, is_active,
                       status, model, scopes, expires_at, last_accessed,
                       last_used_ip, created_at
                FROM api_keys ORDER BY id DESC
                """
            ).fetchall()

    result = []
    for row in rows:
        raw = row["raw_key"] or ""
        prefix = row["key_prefix"] or (raw[:12] if raw else "lan_")
        suffix = row["key_hash"][-6:] if row["key_hash"] else "??????"
        result.append({
            "id": row["id"],
            "name": row["name"],
            "model": row["model"],
            "scopes": (row["scopes"] or "read,write").split(","),
            "status": row["status"] or ("active" if row["is_active"] else "inactive"),
            "is_active": bool(row["is_active"]),
            "masked_key": f"{prefix}...{suffix}",
            "raw_key": raw,
            "expires_at": row["expires_at"],
            "last_accessed": row["last_accessed"],
            "last_used_ip": row["last_used_ip"],
            "created_at": row["created_at"],
        })
    return result


def validate_api_key(raw_key: str, ip_address: str | None = None) -> dict[str, Any] | None:
    """Valida la key, verifica expiración y actualiza last_accessed."""
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    now = now_iso()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT user_id, model, expires_at
            FROM api_keys
            WHERE key_hash = ? AND is_active = 1 AND status != 'archived'
            """,
            (key_hash,),
        ).fetchone()

    if not row:
        return None

    # Verificar expiración
    if row["expires_at"] and row["expires_at"] < now:
        return None

    user = get_user_by_id(row["user_id"])
    if user:
        user["key_model"] = row["model"]
    update_last_accessed(key_hash, ip_address)
    return user


# ─── Audit Log ─────────────────────────────────────────────────────────────

def log_audit_event(
    event_type: str,
    user_id: int | None = None,
    key_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    **metadata,
) -> None:
    """Registra un evento en el audit log."""
    import json as _json
    meta_str = _json.dumps(metadata) if metadata else None
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO audit_events(
                event_type, user_id, key_id, ip_address, user_agent,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, user_id, key_id, ip_address, user_agent, meta_str, now_iso()),
        )
        conn.commit()


# ─── Task Embeddings (vector store en SQLite) ──────────────────────────────

def save_task_embedding(
    user_id: int,
    user_input: str,
    classification: dict[str, Any],
    router_used: str,
    model_called: str | None,
    response_summary: str | None,
    success: bool,
    embedding: list[float],
) -> int:
    """Guarda una tarea con su embedding en la BD. Retorna el id."""
    blob = serialize_vector(embedding) if embedding else None
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO task_embeddings(
                user_id, user_input, intent, complexity, domain, risk_level,
                router_used, model_called, response_summary, success,
                embedding_blob, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_input,
                classification.get("intent"),
                classification.get("complexity"),
                classification.get("domain"),
                classification.get("riskLevel"),
                router_used,
                model_called,
                response_summary,
                1 if success else 0,
                blob,
                now_iso(),
            ),
        )
        conn.commit()
    return cur.lastrowid


def find_similar_tasks(
    user_id: int,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Busca las tareas más similares del usuario usando cosine similarity."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT user_input, intent, complexity, domain, risk_level,
                   router_used, model_called, embedding_blob, created_at
            FROM task_embeddings
            WHERE user_id = ? AND embedding_blob IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,),
        ).fetchall()

    results = []
    for row in rows:
        vec = deserialize_vector(row["embedding_blob"])
        sim = cosine_similarity(query_embedding, vec)
        results.append({
            "user_input": row["user_input"],
            "intent": row["intent"],
            "complexity": row["complexity"],
            "domain": row["domain"],
            "risk_level": row["risk_level"],
            "router_used": row["router_used"],
            "model_called": row["model_called"],
            "similarity": sim,
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


# ─── Conversaciones y mensajes ─────────────────────────────────────────────

def ensure_conversation(
    conversation_id: str, user_id: int, title: str | None, client_id: str | None
) -> None:
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
                conversation_id, role, content, model,
                prompt_tokens, completion_tokens, total_tokens,
                latency_ms, now_iso(),
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
                """,
                (user_id,),
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
        "conversations": 0, "messages": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }


def list_recent_conversations(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT id, COALESCE(title, 'Sin título') AS title, client_id, created_at, updated_at
                FROM conversations WHERE user_id = ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, COALESCE(title, 'Sin título') AS title, client_id, created_at, updated_at
                FROM conversations ORDER BY updated_at DESC LIMIT ?
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
                ORDER BY last_activity DESC LIMIT ?
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
                ORDER BY last_activity DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]
