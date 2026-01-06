import pytest
from openbeepboop.common.db import init_db, get_db_path, get_db_connection
import os
import sqlite3
import tempfile
from unittest.mock import patch

def test_get_db_path_default():
    with patch("openbeepboop.common.db.user_data_dir", return_value="/tmp/openbeepboop"):
        path = get_db_path()
        assert path == "/tmp/openbeepboop/queue.db"

def test_init_db_creates_tables():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        init_db(db_path)

        assert os.path.exists(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check jobs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cursor.fetchone() is not None

        # Check api_keys table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'")
        assert cursor.fetchone() is not None

        conn.close()

def test_get_db_connection_custom_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        init_db(db_path)

        conn = get_db_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row
        conn.close()

def test_get_db_connection_default_path():
     with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "queue.db")

        with patch("openbeepboop.common.db.get_db_path", return_value=db_path):
             init_db() # init at mocked default
             conn = get_db_connection() # get at mocked default
             assert isinstance(conn, sqlite3.Connection)
             conn.close()
