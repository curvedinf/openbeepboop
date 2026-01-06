import pytest
from openbeepboop.server.api import app, get_db_connection, verify_token
from openbeepboop.common.db import init_db
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import shutil
import tempfile
import sqlite3
import hashlib

@pytest.fixture
def test_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_queue.db")

    with patch("openbeepboop.common.db.get_db_path", return_value=db_path):
        init_db(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        key_hash = hashlib.sha256("sk-test".encode()).hexdigest()
        cursor.execute("INSERT INTO api_keys (key_hash, name, role) VALUES (?, ?, ?)", (key_hash, "TestUser", "USER"))
        conn.commit()
        conn.close()

        # We don't patch get_db_connection globally here because we need to control it per test
        # to simulate failure *only* when we want.
        yield db_path

    shutil.rmtree(temp_dir)

@pytest.fixture
def client(test_db):
    # We need to override the dependency for DB connection?
    # No, get_db_connection is a function imported in api.py
    return TestClient(app)

def test_fetch_jobs_db_error(client):
    # Mock verify_token to return success without hitting DB
    app.dependency_overrides[verify_token] = lambda: {"key_hash": "mock", "name": "Node", "role": "NODE"}

    # Mock get_db_connection to return a mock that raises exception on execute
    with patch("openbeepboop.server.api.get_db_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB Error")
        mock_conn.return_value.cursor.return_value = mock_cursor

        response = client.post("/internal/queue/fetch", json={"limit": 1})
        assert response.status_code == 500
        assert "DB Error" in response.json()["detail"]

    app.dependency_overrides = {}

def test_submit_results_db_error(client):
    app.dependency_overrides[verify_token] = lambda: {"key_hash": "mock", "name": "Node", "role": "NODE"}

    with patch("openbeepboop.server.api.get_db_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB Error")
        mock_conn.return_value.cursor.return_value = mock_cursor

        response = client.post("/internal/queue/submit", json=[{"id": "1", "status": "COMPLETED"}])
        assert response.status_code == 500
        assert "DB Error" in response.json()["detail"]

    app.dependency_overrides = {}
