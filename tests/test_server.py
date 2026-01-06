import pytest
from openbeepboop.common.db import init_db
from openbeepboop.common.models import JobStatus
from openbeepboop.client.client import Client
import os
import shutil
import tempfile
import sqlite3
import hashlib
from unittest.mock import MagicMock, patch

# We will test the API directly using TestClient from FastAPI
from fastapi.testclient import TestClient
from openbeepboop.server.api import app

@pytest.fixture
def test_db():
    # Create a temp dir for DB
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_queue.db")

    with patch("openbeepboop.common.db.get_db_path", return_value=db_path):
        init_db(db_path)

        # Add a test API key
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        key_hash = hashlib.sha256("sk-test".encode()).hexdigest()
        cursor.execute("INSERT INTO api_keys (key_hash, name, role) VALUES (?, ?, ?)", (key_hash, "TestUser", "USER"))

        node_key_hash = hashlib.sha256("sk-node".encode()).hexdigest()
        cursor.execute("INSERT INTO api_keys (key_hash, name, role) VALUES (?, ?, ?)", (node_key_hash, "TestNode", "NODE"))

        conn.commit()
        conn.close()

        # Patch get_db_connection in api
        with patch("openbeepboop.server.api.get_db_connection") as mock_get_conn:
            def get_conn(p=None):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                return conn

            mock_get_conn.side_effect = get_conn
            yield db_path

    shutil.rmtree(temp_dir)

@pytest.fixture
def client(test_db):
    return TestClient(app)

def test_auth_missing(client):
    response = client.post("/v1/chat/completions", json={})
    assert response.status_code == 401

def test_auth_invalid(client):
    response = client.post("/v1/chat/completions", json={}, headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401

def test_submit_inference(client):
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    headers = {"Authorization": "Bearer sk-test"}
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["status"] == "QUEUED"

def test_poll_results_empty(client):
    headers = {"Authorization": "Bearer sk-test"}
    response = client.post("/v1/results/poll", json={"ids": []}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert len(data["jobs"]) == 0

def test_fetch_jobs(client, test_db):
    # Submit a job first
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    headers = {"Authorization": "Bearer sk-test"}
    client.post("/v1/chat/completions", json=payload, headers=headers)

    # Fetch as Node
    node_headers = {"Authorization": "Bearer sk-node"}
    response = client.post("/internal/queue/fetch", json={"limit": 1}, headers=node_headers)
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["request_payload"]["model"] == "gpt-4"

    # Check locked_by
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    row = cursor.execute("SELECT locked_by FROM jobs WHERE id = ?", (jobs[0]["id"],)).fetchone()
    assert row[0] == "TestNode"
    conn.close()

def test_submit_results(client):
    # Submit job
    headers = {"Authorization": "Bearer sk-test"}
    resp = client.post("/v1/chat/completions", json={"model": "test", "messages": []}, headers=headers)
    job_id = resp.json()["id"]

    # Fetch job (to lock it)
    node_headers = {"Authorization": "Bearer sk-node"}
    client.post("/internal/queue/fetch", json={"limit": 1}, headers=node_headers)

    # Submit result
    result_payload = {
        "id": job_id,
        "status": "COMPLETED",
        "result": {"choices": [{"message": {"content": "Hi"}}]}
    }
    response = client.post("/internal/queue/submit", json=[result_payload], headers=node_headers)
    assert response.status_code == 200

    # Verify result via poll
    poll_resp = client.post("/v1/results/poll", json={"ids": [job_id]}, headers=headers)
    data = poll_resp.json()
    assert data["jobs"][0]["status"] == "COMPLETED"
    assert data["jobs"][0]["result"]["choices"][0]["message"]["content"] == "Hi"
