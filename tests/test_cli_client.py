import pytest
from typer.testing import CliRunner
from openbeepboop.cli.client import app
from unittest.mock import patch, MagicMock
import json
import os

runner = CliRunner()

@patch("openbeepboop.cli.client.Client")
def test_submit_command(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_client.chat.completions.create.return_value = mock_job

    result = runner.invoke(app, ["submit", "Hello world"])

    assert result.exit_code == 0
    assert "Job submitted successfully. ID: job-123" in result.stdout
    mock_client.chat.completions.create.assert_called_with(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello world"}]
    )

@patch("openbeepboop.cli.client.Client")
def test_submit_command_wait(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.get.return_value = {"result": "success"}
    mock_client.chat.completions.create.return_value = mock_job

    result = runner.invoke(app, ["submit", "Hello world", "--wait"])

    assert result.exit_code == 0
    assert "Waiting for result..." in result.stdout
    assert '"result": "success"' in result.stdout

@patch("openbeepboop.cli.client.Client")
def test_poll_command_completed(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.status = "COMPLETED"
    mock_job.is_completed = True
    mock_job.result = {"content": "response"}

    mock_client.jobs.poll.return_value = [mock_job]

    result = runner.invoke(app, ["poll", "job-123"])

    assert result.exit_code == 0
    assert "Status: COMPLETED" in result.stdout
    assert '"content": "response"' in result.stdout

@patch("openbeepboop.cli.client.Client")
def test_poll_command_not_completed(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.status = "QUEUED"
    mock_job.is_completed = False

    mock_client.jobs.poll.return_value = [mock_job]

    result = runner.invoke(app, ["poll", "job-123"])

    assert result.exit_code == 0
    assert "Status: QUEUED" in result.stdout

@patch("openbeepboop.cli.client.Client")
def test_poll_command_wait(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_job = MagicMock()
    mock_job.id = "job-123"
    mock_job.status = "QUEUED"
    mock_job.is_completed = False # Initially false

    # Mocking get(wait=True) to return result
    mock_job.get.return_value = {"content": "final"}

    mock_client.jobs.poll.return_value = [mock_job]

    result = runner.invoke(app, ["poll", "job-123", "--wait"])

    assert result.exit_code == 0
    assert "Waiting for result..." in result.stdout
    assert '"content": "final"' in result.stdout

@patch("openbeepboop.cli.client.Client")
def test_poll_command_not_found(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.jobs.poll.return_value = []

    result = runner.invoke(app, ["poll", "job-999"])

    assert result.exit_code == 1
    assert "Job job-999 not found" in result.stderr

@patch("openbeepboop.cli.client.Client")
def test_submit_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Submit failed")

    result = runner.invoke(app, ["submit", "Hello"])
    assert result.exit_code == 1
    assert "Error submitting job: Submit failed" in result.stderr

def test_client_setup_command():
    with runner.isolated_filesystem():
        # Input: server_url, api_key (optional - empty)
        input_str = "http://custom-server:9000\n\n"
        result = runner.invoke(app, ["setup"], input=input_str)

        assert result.exit_code == 0
        assert "client_config.toml created" in result.stdout

        # Verify content
        with open("client_config.toml", "rb") as f:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            config = tomllib.load(f)

        assert config["server"]["url"] == "http://custom-server:9000"
        assert config["server"].get("api_key") is None

@patch("openbeepboop.cli.client.Client")
def test_submit_command_with_config(mock_client_cls):
    # Mock loading config by creating a file in isolated fs
    with runner.isolated_filesystem():
        with open("client_config.toml", "w") as f:
            f.write('[server]\nurl = "http://config-server:8000"\napi_key = "config-key"')

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_job = MagicMock()
        mock_job.id = "job-config"
        mock_client.chat.completions.create.return_value = mock_job

        # Run command without explicit args
        result = runner.invoke(app, ["submit", "Test"])

        assert result.exit_code == 0

        # Verify Client was initialized with config values
        mock_client_cls.assert_called_with(base_url="http://config-server:8000", api_key="config-key")

@patch("openbeepboop.cli.client.Client")
def test_submit_command_override_config(mock_client_cls):
    # Mock loading config
    with runner.isolated_filesystem():
        with open("client_config.toml", "w") as f:
            f.write('[server]\nurl = "http://config-server:8000"\napi_key = "config-key"')

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_job = MagicMock()
        mock_job.id = "job-override"
        mock_client.chat.completions.create.return_value = mock_job

        # Run command WITH explicit args
        result = runner.invoke(app, ["submit", "Test", "--server-url", "http://override:5000"])

        assert result.exit_code == 0

        # Verify Client was initialized with OVERRIDDEN values
        mock_client_cls.assert_called_with(base_url="http://override:5000", api_key="config-key")
