from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "app.db")
_USE_PG = bool(DATABASE_URL)

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None



# ---------------- basic helpers ----------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, iterations: int = 390000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt_b64, digest_b64 = str(stored).split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


@contextmanager
def _pg_conn():
    if psycopg is None:
        raise RuntimeError("psycopg is required for Postgres. Add 'psycopg[binary]' to requirements.txt.")
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)  # type: ignore[arg-type]
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _sqlite_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_SQLITE_SINGLETON: Optional[sqlite3.Connection] = None


def _sqlite_singleton() -> sqlite3.Connection:
    global _SQLITE_SINGLETON
    if _SQLITE_SINGLETON is None:
        _SQLITE_SINGLETON = _sqlite_conn()
    return _SQLITE_SINGLETON


def _rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
        elif isinstance(row, sqlite3.Row):
            out.append({k: row[k] for k in row.keys()})
        else:
            try:
                out.append(dict(row))
            except Exception:
                out.append({})
    return out


def _exec(sql: str, params: Tuple[Any, ...] = (), fetch: str = "none") -> Any:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None
    conn = _sqlite_singleton()
    cur = conn.cursor()
    cur.execute(sql, params)
    if fetch == "one":
        row = cur.fetchone()
        conn.commit()
        return row
    if fetch == "all":
        rows = cur.fetchall()
        conn.commit()
        return rows
    conn.commit()
    return None


def _has_column(table: str, col: str) -> bool:
    if _USE_PG:
        row = _exec(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            LIMIT 1
            """,
            (table, col),
            fetch="one",
        )
        return bool(row)
    rows = _exec(f"PRAGMA table_info({table})", fetch="all")
    for r in rows:
        d = {k: r[k] for k in r.keys()}  # type: ignore[attr-defined]
        if d.get("name") == col:
            return True
    return False


def _add_column(table: str, col: str, col_type_sql: str) -> None:
    if _has_column(table, col):
        return
    _exec(f"ALTER TABLE {table} ADD COLUMN {col} {col_type_sql}")


# ---------------- schema ----------------


def init_db() -> None:
    _exec(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    _exec(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    _exec(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    if _USE_PG:
        _exec(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                analysis_uid TEXT UNIQUE,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                title TEXT,
                source_filename TEXT,
                transcript_text TEXT,
                meta_json TEXT,
                report_text TEXT,
                recommendation_text TEXT,
                model_snapshot TEXT,
                system_prompt_snapshot TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    else:
        _exec(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY,
                analysis_uid TEXT UNIQUE,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                title TEXT,
                source_filename TEXT,
                transcript_text TEXT,
                meta_json TEXT,
                report_text TEXT,
                recommendation_text TEXT,
                model_snapshot TEXT,
                system_prompt_snapshot TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    _add_column("analyses", "analysis_uid", "TEXT")
    _add_column("analyses", "source_filename", "TEXT")
    _add_column("analyses", "transcript_text", "TEXT")
    _add_column("analyses", "meta_json", "TEXT")
    _add_column("analyses", "report_text", "TEXT")
    _add_column("analyses", "recommendation_text", "TEXT")
    _add_column("analyses", "model_snapshot", "TEXT")
    _add_column("analyses", "system_prompt_snapshot", "TEXT")

    if _USE_PG:
        _exec(
            "CREATE UNIQUE INDEX IF NOT EXISTS analyses_analysis_uid_idx ON analyses (analysis_uid) WHERE analysis_uid IS NOT NULL"
        )
    else:
        _exec("CREATE UNIQUE INDEX IF NOT EXISTS analyses_analysis_uid_idx ON analyses (analysis_uid)")

    rows = _exec("SELECT id FROM analyses WHERE analysis_uid IS NULL OR analysis_uid = ''", fetch="all")
    for row in _rows_to_dicts(rows):
        aid = int(row.get("id"))
        _exec(
            "UPDATE analyses SET analysis_uid = ? WHERE id = ?" if not _USE_PG else "UPDATE analyses SET analysis_uid = %s WHERE id = %s",
            (uuid.uuid4().hex, aid),
        )


# ---------------- settings ----------------


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = _exec(
        "SELECT value FROM settings WHERE key = ?" if not _USE_PG else "SELECT value FROM settings WHERE key = %s",
        (key,),
        fetch="one",
    )
    if not row:
        return default
    return row.get("value") if isinstance(row, dict) else row[0]


def set_setting(key: str, value: str) -> None:
    if _USE_PG:
        _exec(
            """
            INSERT INTO settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, value),
        )
    else:
        _exec(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_system_prompt(default: str) -> str:
    return str(get_setting("system_prompt", default) or default)


def set_system_prompt(prompt: str) -> None:
    set_setting("system_prompt", prompt or "")


def get_active_model(default: str) -> str:
    return str(get_setting("active_model", default) or default)


def set_active_model(model: str) -> None:
    set_setting("active_model", model or "")


# ---------------- users / auth ----------------


def any_admin_exists() -> bool:
    row = _exec(
        "SELECT 1 FROM users WHERE role = ? LIMIT 1" if not _USE_PG else "SELECT 1 FROM users WHERE role = %s LIMIT 1",
        ("admin",),
        fetch="one",
    )
    return bool(row)


def upsert_user(user_id: str, password: str, role: str) -> None:
    pw_hash = _hash_password(password)
    if _USE_PG:
        _exec(
            """
            INSERT INTO users (user_id, password_hash, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role
            """,
            (user_id, pw_hash, role),
        )
    else:
        _exec(
            """
            INSERT INTO users (user_id, password_hash, role)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET password_hash = excluded.password_hash, role = excluded.role
            """,
            (user_id, pw_hash, role),
        )


def set_user_password(user_id: str, new_password: str) -> bool:
    if not str(new_password or "").strip():
        return False
    pw_hash = _hash_password(new_password)
    _exec(
        "UPDATE users SET password_hash = ? WHERE user_id = ?" if not _USE_PG else "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (pw_hash, user_id),
    )
    return True


def verify_user(user_id: str, password: str) -> Optional[Dict[str, str]]:
    row = _exec(
        "SELECT user_id, password_hash, role FROM users WHERE user_id = ?" if not _USE_PG else "SELECT user_id, password_hash, role FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )
    if not row:
        return None

    data = row if isinstance(row, dict) else {"user_id": row[0], "password_hash": row[1], "role": row[2]}
    stored = data.get("password_hash")
    if stored is None:
        return None
    if isinstance(stored, (bytes, bytearray)):
        stored = stored.decode("utf-8", errors="ignore")
    stored = str(stored).strip()

    ok = False
    used_plaintext = False
    if stored.startswith("pbkdf2_sha256$"):
        ok = _verify_password(password, stored)
    else:
        used_plaintext = True
        ok = hmac.compare_digest(password, stored)

    if not ok:
        return None

    if used_plaintext:
        new_hash = _hash_password(password)
        _exec(
            "UPDATE users SET password_hash = ? WHERE user_id = ?" if not _USE_PG else "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_hash, user_id),
        )

    return {"user_id": str(data.get("user_id") or ""), "role": str(data.get("role") or "user")}


def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    auth = verify_user(user_id, current_password)
    if not auth:
        return False
    return set_user_password(user_id, new_password)


def list_users() -> List[Dict[str, Any]]:
    rows = _exec("SELECT user_id, role FROM users ORDER BY user_id", fetch="all")
    return _rows_to_dicts(rows)


# ---------------- sessions ----------------


def create_session(user_id: str, role: str, hours: int = 12) -> str:
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=hours)
    _exec(
        """
        INSERT INTO sessions (token, user_id, role, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """
        if not _USE_PG
        else
        """
        INSERT INTO sessions (token, user_id, role, created_at, expires_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (token, user_id, role, now.isoformat(), expires.isoformat()),
    )
    return token


def get_session(token: str) -> Optional[Dict[str, Any]]:
    row = _exec(
        "SELECT token, user_id, role, expires_at FROM sessions WHERE token = ?" if not _USE_PG else "SELECT token, user_id, role, expires_at FROM sessions WHERE token = %s",
        (token,),
        fetch="one",
    )
    if not row:
        return None
    data = row if isinstance(row, dict) else {"token": row[0], "user_id": row[1], "role": row[2], "expires_at": row[3]}
    try:
        exp = datetime.fromisoformat(str(data.get("expires_at") or ""))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            delete_session(token)
            return None
    except Exception:
        pass
    return {"token": str(data.get("token") or ""), "user_id": str(data.get("user_id") or ""), "role": str(data.get("role") or "user")}


def delete_session(token: str) -> None:
    _exec(
        "DELETE FROM sessions WHERE token = ?" if not _USE_PG else "DELETE FROM sessions WHERE token = %s",
        (token,),
    )


# ---------------- analyses ----------------


def create_analysis(
    user_id: str,
    role: str,
    title: str,
    source_filename: str,
    transcript_text: str,
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    now = _now_iso()
    analysis_uid = uuid.uuid4().hex
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    if _USE_PG:
        row = _exec(
            """
            INSERT INTO analyses (
                analysis_uid, user_id, role, title, source_filename, transcript_text,
                meta_json, report_text, recommendation_text, model_snapshot,
                system_prompt_snapshot, created_at, updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                analysis_uid,
                user_id,
                role,
                title,
                source_filename,
                transcript_text,
                meta_json,
                "",
                "",
                "",
                "",
                now,
                now,
            ),
            fetch="one",
        )
        return int(row["id"])  # type: ignore[index]

    _exec(
        """
        INSERT INTO analyses (
            analysis_uid, user_id, role, title, source_filename, transcript_text,
            meta_json, report_text, recommendation_text, model_snapshot,
            system_prompt_snapshot, created_at, updated_at
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            analysis_uid,
            user_id,
            role,
            title,
            source_filename,
            transcript_text,
            meta_json,
            "",
            "",
            "",
            "",
            now,
            now,
        ),
    )
    row = _exec("SELECT last_insert_rowid() AS id", fetch="one")
    return int(row["id"])  # type: ignore[index]


def update_analysis(
    analysis_id: int,
    *,
    title: Optional[str] = None,
    source_filename: Optional[str] = None,
    transcript_text: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    report_text: Optional[str] = None,
    recommendation_text: Optional[str] = None,
    model_snapshot: Optional[str] = None,
    system_prompt_snapshot: Optional[str] = None,
) -> None:
    now = _now_iso()
    sets = ["updated_at = ?" if not _USE_PG else "updated_at = %s"]
    params: List[Any] = [now]

    if title is not None:
        sets.append("title = ?" if not _USE_PG else "title = %s")
        params.append(title)
    if source_filename is not None:
        sets.append("source_filename = ?" if not _USE_PG else "source_filename = %s")
        params.append(source_filename)
    if transcript_text is not None:
        sets.append("transcript_text = ?" if not _USE_PG else "transcript_text = %s")
        params.append(transcript_text)
    if meta is not None:
        sets.append("meta_json = ?" if not _USE_PG else "meta_json = %s")
        params.append(json.dumps(meta, ensure_ascii=False))
    if report_text is not None:
        sets.append("report_text = ?" if not _USE_PG else "report_text = %s")
        params.append(report_text)
    if recommendation_text is not None:
        sets.append("recommendation_text = ?" if not _USE_PG else "recommendation_text = %s")
        params.append(recommendation_text)
    if model_snapshot is not None:
        sets.append("model_snapshot = ?" if not _USE_PG else "model_snapshot = %s")
        params.append(model_snapshot)
    if system_prompt_snapshot is not None:
        sets.append("system_prompt_snapshot = ?" if not _USE_PG else "system_prompt_snapshot = %s")
        params.append(system_prompt_snapshot)

    params.append(analysis_id)
    sql = (
        f"UPDATE analyses SET {', '.join(sets)} WHERE id = ?"
        if not _USE_PG
        else f"UPDATE analyses SET {', '.join(sets)} WHERE id = %s"
    )
    _exec(sql, tuple(params))


def get_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    row = _exec(
        "SELECT * FROM analyses WHERE id = ?" if not _USE_PG else "SELECT * FROM analyses WHERE id = %s",
        (analysis_id,),
        fetch="one",
    )
    if not row:
        return None
    data = row if isinstance(row, dict) else {k: row[k] for k in row.keys()}  # type: ignore[attr-defined]
    try:
        data["meta"] = json.loads(data.get("meta_json") or "{}")
    except Exception:
        data["meta"] = {}
    return data


def list_analyses_for_user(user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    rows = _exec(
        """
        SELECT id, analysis_uid, title, source_filename, updated_at, created_at,
               model_snapshot, user_id
        FROM analyses
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """
        if not _USE_PG
        else
        """
        SELECT id, analysis_uid, title, source_filename, updated_at, created_at,
               model_snapshot, user_id
        FROM analyses
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (user_id, limit),
        fetch="all",
    )
    return _rows_to_dicts(rows)
