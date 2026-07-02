import hashlib
import json as _json
import math
import secrets
import struct
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
import mysql.connector
from mysql.connector import pooling

from app.config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    MYSQL_POOL_SIZE,
    KEY_EXPIRY_DAYS,
)

INACTIVE_ARCHIVE_DAYS = 30

# Inicialización del Pool de Conexiones
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="folax_pool",
            pool_size=MYSQL_POOL_SIZE,
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
            autocommit=False
        )
    return _pool

@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    import os
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${dk.hex()}"

def _verify_password_internal(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("scrypt$"):
        try:
            _, salt_hex, dk_hex = stored_hash.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
            return dk.hex() == dk_hex
        except Exception:
            return False
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash

def serialize_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)

def deserialize_vector(blob: bytes) -> tuple[float, ...]:
    n = len(blob) // 4
    return struct.unpack(f"{n}f", blob)

def cosine_similarity(v1: Any, v2: Any) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def init_db() -> None:
    # Intentamos crear las tablas directamente si la base de datos ya existe
    # El archivo schema_mysql.sql se usa para inicializar a mano en Railway,
    # pero aquí hacemos una inicialización automática básica de seguridad.
    with get_conn() as conn:
        cursor = conn.cursor()
        
        # Tabla users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # Tabla api_keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(255) NOT NULL UNIQUE,
                key_prefix VARCHAR(255) NULL,
                raw_key VARCHAR(255) NULL,
                is_active TINYINT NOT NULL DEFAULT 1,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                scopes VARCHAR(255) NOT NULL DEFAULT 'read,write',
                model VARCHAR(255) NULL,
                expires_at VARCHAR(255) NULL,
                last_accessed VARCHAR(255) NULL,
                last_used_ip VARCHAR(100) NULL,
                deactivated_at VARCHAR(255) NULL,
                created_at VARCHAR(255) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla conversations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR(255) PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(255) NULL,
                client_id VARCHAR(255) NULL,
                created_at VARCHAR(255) NOT NULL,
                updated_at VARCHAR(255) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                conversation_id VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                model VARCHAR(255) NULL,
                prompt_tokens INT NOT NULL DEFAULT 0,
                completion_tokens INT NOT NULL DEFAULT 0,
                total_tokens INT NOT NULL DEFAULT 0,
                latency_ms INT NOT NULL DEFAULT 0,
                created_at VARCHAR(255) NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla audit_events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                user_id INT NULL,
                key_id INT NULL,
                ip_address VARCHAR(100) NULL,
                user_agent VARCHAR(255) NULL,
                metadata_json TEXT NULL,
                created_at VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla task_embeddings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                user_input TEXT NOT NULL,
                intent VARCHAR(255) NULL,
                complexity DOUBLE NULL,
                domain VARCHAR(255) NULL,
                risk_level VARCHAR(50) NULL,
                router_used VARCHAR(255) NULL,
                model_called VARCHAR(255) NULL,
                response_summary TEXT NULL,
                success TINYINT NOT NULL DEFAULT 1,
                embedding_blob MEDIUMBLOB NULL,
                created_at VARCHAR(255) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla app_versions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(50) NOT NULL UNIQUE,
                channel VARCHAR(50) NOT NULL DEFAULT 'stable',
                release_date VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                changelog_json TEXT NOT NULL,
                download_url VARCHAR(512) NOT NULL,
                checksum_sha256 VARCHAR(255) NULL,
                created_at VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Tabla token_usage_daily
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage_daily (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                usage_date DATE NOT NULL,
                model VARCHAR(255) NOT NULL,
                prompt_tokens INT NOT NULL DEFAULT 0,
                completion_tokens INT NOT NULL DEFAULT 0,
                total_tokens INT NOT NULL DEFAULT 0,
                latency_sum_ms INT NOT NULL DEFAULT 0,
                request_count INT NOT NULL DEFAULT 0,
                created_at VARCHAR(255) NOT NULL,
                UNIQUE KEY uq_user_date_model (user_id, usage_date, model),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # Índices adicionales
        try:
            cursor.execute("CREATE INDEX idx_api_keys_user_active ON api_keys(user_id, is_active)")
            cursor.execute("CREATE INDEX idx_api_keys_composite ON api_keys(user_id, is_active, created_at)")
            cursor.execute("CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at)")
            cursor.execute("CREATE INDEX idx_messages_conv ON messages(conversation_id, created_at)")
            cursor.execute("CREATE INDEX idx_audit_user_type ON audit_events(user_id, event_type, created_at)")
            cursor.execute("CREATE INDEX idx_task_emb_user ON task_embeddings(user_id, created_at DESC)")
            cursor.execute("CREATE INDEX idx_token_usage_date ON token_usage_daily(usage_date)")
        except mysql.connector.Error:
            pass # Los índices ya existen

        conn.commit()

def create_user(username: str, password: str) -> dict[str, Any] | None:
    try:
        pw_hash = hash_password(password)
        created_at = now_iso()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (%s, %s, %s)",
                (username, pw_hash, created_at),
            )
            user_id = cursor.lastrowid
            conn.commit()
            return {"id": user_id, "username": username}
    except mysql.connector.Error as err:
        if err.errno == 1062: # Duplicate entry
            return None
        raise

def verify_user(username: str, password: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        if not _verify_password_internal(password, row["password_hash"]):
            return None
        
        if not row["password_hash"].startswith("scrypt$"):
            new_hash = hash_password(password)
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_hash, row["id"]),
            )
            conn.commit()
        return {"id": row["id"], "username": row["username"]}

def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username FROM users WHERE id = %s", (user_id,)
        )
        row = cursor.fetchone()
    return row

def _key_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=KEY_EXPIRY_DAYS)).isoformat()

def get_active_key_for_user(user_id: int) -> dict[str, Any] | None:
    now = now_iso()
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, raw_key, expires_at, scopes, model, key_prefix, created_at
            FROM api_keys
            WHERE user_id = %s
              AND is_active = 1
              AND status = 'active'
              AND expires_at > %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, now),
        )
        row = cursor.fetchone()
    return row

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
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO api_keys(
                user_id, name, key_hash, raw_key, key_prefix,
                is_active, status, scopes, model,
                expires_at, last_accessed, created_at
            ) VALUES (%s, %s, %s, %s, %s, 1, 'active', %s, %s, %s, %s, %s)
            """,
            (user_id, name, key_hash, raw_key, key_prefix,
             scopes, model, expires_at, created_at, created_at),
        )
        key_id = cursor.lastrowid
        conn.commit()
        key_data = {
            "id": key_id,
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
    now = now_iso()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE api_keys
            SET is_active = 0, status = 'inactive', deactivated_at = %s
            WHERE id = %s
            """,
            (now, key_id),
        )
        conn.commit()
    return True

def deactivate_all_user_keys(user_id: int) -> None:
    now = now_iso()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE api_keys
            SET is_active = 0, status = 'inactive', deactivated_at = %s
            WHERE user_id = %s AND is_active = 1
            """,
            (now, user_id),
        )
        conn.commit()

def update_last_accessed(key_hash: str, ip_address: str | None) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_keys SET last_accessed = %s, last_used_ip = %s WHERE key_hash = %s",
            (now_iso(), ip_address, key_hash),
        )
        conn.commit()

def archive_old_inactive_keys() -> int:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=INACTIVE_ARCHIVE_DAYS)
    ).isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE api_keys
            SET status = 'archived'
            WHERE status = 'inactive' AND deactivated_at < %s
            """,
            (cutoff,),
        )
        conn.commit()
        count = cursor.rowcount
    return count

def count_daily_regenerations(user_id: int) -> int:
    today_start = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE user_id = %s AND event_type = 'api_key_regenerated' AND created_at >= %s
            """,
            (user_id, today_start),
        )
        row = cursor.fetchone()
    return row[0] if row else 0

def list_api_keys(user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        if user_id is not None:
            cursor.execute(
                """
                SELECT id, name, key_hash, raw_key, key_prefix, is_active,
                       status, model, scopes, expires_at, last_accessed,
                       last_used_ip, created_at
                FROM api_keys
                WHERE user_id = %s
                ORDER BY id DESC
                """,
                (user_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, key_hash, raw_key, key_prefix, is_active,
                       status, model, scopes, expires_at, last_accessed,
                       last_used_ip, created_at
                FROM api_keys ORDER BY id DESC
                """
            )
        rows = cursor.fetchall()

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
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    now = now_iso()
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id, model, expires_at
            FROM api_keys
            WHERE key_hash = %s AND is_active = 1 AND status != 'archived'
            """,
            (key_hash,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    if row["expires_at"] and row["expires_at"] < now:
        return None

    user = get_user_by_id(row["user_id"])
    if user:
        user["key_model"] = row["model"]
    update_last_accessed(key_hash, ip_address)
    return user

def log_audit_event(
    event_type: str,
    user_id: int | None = None,
    key_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    **metadata,
) -> None:
    meta_str = _json.dumps(metadata) if metadata else None
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_events(
                event_type, user_id, key_id, ip_address, user_agent,
                metadata_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (event_type, user_id, key_id, ip_address, user_agent, meta_str, now_iso()),
        )
        conn.commit()

def list_audit_events(
    user_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        if user_id is not None:
            cursor.execute(
                """
                SELECT id, event_type, key_id, ip_address, metadata_json, created_at
                FROM audit_events
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, event_type, user_id, key_id, ip_address, metadata_json, created_at
                FROM audit_events
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall()
    result = []
    for row in rows:
        r = dict(row)
        if r.get("metadata_json"):
            try:
                r["metadata"] = _json.loads(r.pop("metadata_json"))
            except Exception:
                r["metadata"] = {}
        else:
            r.pop("metadata_json", None)
            r["metadata"] = {}
        result.append(r)
    return result

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
    blob = serialize_vector(embedding) if embedding else None
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO task_embeddings(
                user_id, user_input, intent, complexity, domain, risk_level,
                router_used, model_called, response_summary, success,
                embedding_blob, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        task_id = cursor.lastrowid
        conn.commit()
    return task_id

def find_similar_tasks(
    user_id: int,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_input, intent, complexity, domain, risk_level,
                   router_used, model_called, embedding_blob, created_at
            FROM task_embeddings
            WHERE user_id = %s AND embedding_blob IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

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

def ensure_conversation(
    conversation_id: str, user_id: int, title: str | None, client_id: str | None
) -> None:
    ts = now_iso()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM conversations WHERE id = %s", (conversation_id,)
        )
        exists = cursor.fetchone()
        if exists:
            cursor.execute(
                "UPDATE conversations SET updated_at = %s, title = COALESCE(%s, title), client_id = COALESCE(%s, client_id) WHERE id = %s",
                (ts, title, client_id, conversation_id),
            )
        else:
            cursor.execute(
                "INSERT INTO conversations(id, user_id, title, client_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
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
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages(
                conversation_id, role, content, model, prompt_tokens,
                completion_tokens, total_tokens, latency_ms, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                conversation_id, role, content, model,
                prompt_tokens, completion_tokens, total_tokens,
                latency_ms, now_iso(),
            ),
        )
        cursor.execute(
            "UPDATE conversations SET updated_at = %s WHERE id = %s",
            (now_iso(), conversation_id),
        )
        
        # Registrar o actualizar métricas agregadas en token_usage_daily
        cursor.execute(
            "SELECT user_id FROM conversations WHERE id = %s", (conversation_id,)
        )
        conv = cursor.fetchone()
        if conv:
            user_id = conv[0]
            today = datetime.now(timezone.utc).date()
            cursor.execute(
                """
                INSERT INTO token_usage_daily (
                    user_id, usage_date, model, prompt_tokens,
                    completion_tokens, total_tokens, latency_sum_ms,
                    request_count, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    prompt_tokens = prompt_tokens + VALUES(prompt_tokens),
                    completion_tokens = completion_tokens + VALUES(completion_tokens),
                    total_tokens = total_tokens + VALUES(total_tokens),
                    latency_sum_ms = latency_sum_ms + VALUES(latency_sum_ms),
                    request_count = request_count + 1
                """,
                (user_id, today, model or "default", prompt_tokens,
                 completion_tokens, total_tokens, latency_ms, now_iso())
            )
            
        conn.commit()

def get_usage_summary(user_id: int | None = None) -> dict[str, int]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        if user_id is not None:
            cursor.execute(
                """
                SELECT
                    COUNT(DISTINCT c.id) AS conversations,
                    COUNT(m.id) AS messages,
                    COALESCE(SUM(m.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(m.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(m.total_tokens), 0) AS total_tokens
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = %s
                """,
                (user_id,),
            )
        else:
            cursor.execute(
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
            )
        row = cursor.fetchone()
    return row if row else {
        "conversations": 0, "messages": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }

def list_recent_conversations(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        if user_id is not None:
            cursor.execute(
                """
                SELECT id, COALESCE(title, 'Sin título') AS title, client_id, created_at, updated_at
                FROM conversations WHERE user_id = %s
                ORDER BY updated_at DESC LIMIT %s
                """,
                (user_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, COALESCE(title, 'Sin título') AS title, client_id, created_at, updated_at
                FROM conversations ORDER BY updated_at DESC LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall()
    return rows

def list_clients_usage(limit: int = 50, user_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        if user_id is not None:
            cursor.execute(
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
                WHERE c.user_id = %s
                GROUP BY COALESCE(c.client_id, 'sin_client_id')
                ORDER BY last_activity DESC LIMIT %s
                """,
                (user_id, limit),
            )
        else:
            cursor.execute(
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
                ORDER BY last_activity DESC LIMIT %s
                """,
                (limit,),
            )
        rows = cursor.fetchall()
    return rows

# Funciones de soporte para Gestión de Versiones (app_versions)
def get_all_versions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM app_versions ORDER BY release_date DESC")
        rows = cursor.fetchall()
    for row in rows:
        try:
            row["changelog"] = _json.loads(row.pop("changelog_json"))
        except Exception:
            row["changelog"] = []
    return rows

def get_latest_version(channel: str = "stable") -> dict[str, Any] | None:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM app_versions WHERE channel = %s ORDER BY release_date DESC LIMIT 1",
            (channel,)
        )
        row = cursor.fetchone()
    if row:
        try:
            row["changelog"] = _json.loads(row.pop("changelog_json"))
        except Exception:
            row["changelog"] = []
    return row

def add_app_version(
    version: str, channel: str, release_date: str, title: str,
    changelog: list[str], download_url: str, checksum: str | None = None
) -> None:
    changelog_str = _json.dumps(changelog)
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO app_versions (
                version, channel, release_date, title, changelog_json,
                download_url, checksum_sha256, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                channel = VALUES(channel), release_date = VALUES(release_date),
                title = VALUES(title), changelog_json = VALUES(changelog_json),
                download_url = VALUES(download_url), checksum_sha256 = VALUES(checksum_sha256)
            """,
            (version, channel, release_date, title, changelog_str, download_url, checksum, now_iso())
        )
        conn.commit()

# Funciones de soporte para Métricas (token_usage_daily)
def get_daily_metrics(user_id: int, days_limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT usage_date, model, prompt_tokens, completion_tokens, total_tokens, latency_sum_ms, request_count
            FROM token_usage_daily
            WHERE user_id = %s
            ORDER BY usage_date DESC
            LIMIT %s
            """,
            (user_id, days_limit)
        )
        rows = cursor.fetchall()
    return rows
