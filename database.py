import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "checker.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS laws (
            name        TEXT PRIMARY KEY,
            search_name TEXT,
            text        TEXT,
            fetched_at  TEXT,
            char_count  INTEGER,
            error       INTEGER DEFAULT 0,
            error_msg   TEXT
        );

        CREATE TABLE IF NOT EXISTS dict_meta (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            dict_date   TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            judge       TEXT,
            result      TEXT,
            summary     TEXT,
            formatted   TEXT,
            dict_date   TEXT,
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            done_at     TEXT
        );
        """)


def upsert_law(name, search_name, text, fetched_at, error=False, error_msg=""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO laws (name, search_name, text, fetched_at, char_count, error, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                search_name = excluded.search_name,
                text        = excluded.text,
                fetched_at  = excluded.fetched_at,
                char_count  = excluded.char_count,
                error       = excluded.error,
                error_msg   = excluded.error_msg
        """, (name, search_name, text, fetched_at, len(text), int(error), error_msg))


def get_all_laws():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM laws").fetchall()
        return [dict(r) for r in rows]


def get_law(name):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM laws WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def get_dict_meta():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM dict_meta WHERE id = 1").fetchone()
        return dict(row) if row else {}


def set_dict_meta(dict_date):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO dict_meta (id, dict_date, updated_at)
            VALUES (1, ?, datetime('now', 'localtime'))
            ON CONFLICT(id) DO UPDATE SET
                dict_date  = excluded.dict_date,
                updated_at = excluded.updated_at
        """, (dict_date,))


def clear_laws():
    with get_conn() as conn:
        conn.execute("DELETE FROM laws")
        conn.execute("DELETE FROM dict_meta")


def create_job(question, formatted, dict_date):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (question, formatted, dict_date) VALUES (?, ?, ?)",
            (question, formatted, dict_date)
        )
        return cur.lastrowid


def create_jobs_bulk(rows, dict_date):
    with get_conn() as conn:
        ids = []
        for question, formatted in rows:
            cur = conn.execute(
                "INSERT INTO jobs (question, formatted, dict_date) VALUES (?, ?, ?)",
                (question, formatted, dict_date)
            )
            ids.append(cur.lastrowid)
        return ids


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_pending_jobs(limit=1):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_job(job_id, status, judge=None, result=None, summary=None):
    with get_conn() as conn:
        conn.execute("""
            UPDATE jobs SET
                status  = ?,
                judge   = ?,
                result  = ?,
                summary = ?,
                done_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (status, judge, result, summary, job_id))


def get_jobs_by_ids(ids):
    placeholders = ",".join("?" * len(ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE id IN ({placeholders}) ORDER BY id", ids
        ).fetchall()
        return [dict(r) for r in rows]
