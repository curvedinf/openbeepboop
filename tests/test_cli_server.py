import pytest
from typer.testing import CliRunner
from openbeepboop.cli.server import app
from unittest.mock import patch, MagicMock
import os
import shutil
import tempfile

runner = CliRunner()

def test_server_setup_command():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")

        with patch("openbeepboop.cli.server.get_db_path", return_value=db_path):
            # Simulate user input: accepts default path
            result = runner.invoke(app, ["setup"], input="\n")

            assert result.exit_code == 0
            assert f"Database initialized at {db_path}" in result.stdout
            assert "Setup complete. Your Admin Key is: sk-" in result.stdout

            # Check if DB was created and admin key inserted
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM api_keys WHERE role='ADMIN'").fetchall()
            assert len(rows) == 1
            assert rows[0][1] == "Admin" # name
            conn.close()

def test_server_setup_command_custom_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        default_db = os.path.join(temp_dir, "default.db")
        custom_db = os.path.join(temp_dir, "custom.db")

        with patch("openbeepboop.cli.server.get_db_path", return_value=default_db):
            # Simulate user input: enters custom path
            result = runner.invoke(app, ["setup"], input=f"{custom_db}\n")

            assert result.exit_code == 0
            assert f"Database initialized at {custom_db}" in result.stdout
            assert os.path.exists(custom_db)

@patch("openbeepboop.cli.server.uvicorn.run")
def test_server_start_command(mock_run):
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert "openbeepboop.server.api:app" in args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000

@patch("openbeepboop.cli.server.uvicorn.run")
def test_server_start_command_custom_host_port(mock_run):
    result = runner.invoke(app, ["start", "--host", "127.0.0.1", "--port", "9000"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9000

def test_server_setup_duplicate_key_handling():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")

        with patch("openbeepboop.cli.server.get_db_path", return_value=db_path):
            with patch("openbeepboop.cli.server.secrets.token_hex", return_value="fixedtoken"):
                # First run
                runner.invoke(app, ["setup"], input="\n")

                # Second run (should encounter integrity error but handle it)
                result = runner.invoke(app, ["setup"], input="\n")
                assert "Admin key already exists" in result.stdout
