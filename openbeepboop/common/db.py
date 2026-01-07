import sqlite3
import os
from platformdirs import user_data_dir
from openbeepboop.common.models import Job
import json
from datetime import datetime

APP_NAME = "openbeepboop"

def get_db_path():
    data_dir = user_data_dir(APP_NAME, ensure_exists=True)
    return os.path.join(data_dir, "queue.db")

def init_db(db_path: str = None):
    if db_path is None:
        db_path = get_db_path()

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        created_at DATETIME,
        updated_at DATETIME,
        request_payload TEXT,
        result_payload TEXT,
        locked_by TEXT,
        locked_at DATETIME,
        priority INTEGER DEFAULT 0
    )
    """)

    # Simple migration: check if priority column exists, if not add it
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [info[1] for info in cursor.fetchall()]
    if "priority" not in columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 0")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        key_hash TEXT PRIMARY KEY,
        name TEXT,
        role TEXT
    )
    """)

    conn.commit()
    conn.close()
    return db_path

def get_db_connection(db_path: str = None):
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
