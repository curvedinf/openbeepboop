import pytest
from typer.testing import CliRunner
from openbeepboop.cli.node import app
from unittest.mock import patch, MagicMock, mock_open
import os
import tomli_w
import tempfile

runner = CliRunner()

def test_node_setup_command():
    with runner.isolated_filesystem():
        # Input: server_url, api_key, local? (n), model
        input_str = "http://myserver:8000\nsk-mykey\nn\ngpt-4o\n"
        result = runner.invoke(app, ["setup"], input=input_str)

        assert result.exit_code == 0
        assert "node_config.toml created" in result.stdout

        with open("node_config.toml", "rb") as f:
            import tomli
            config = tomli.load(f)

        assert config["server"]["url"] == "http://myserver:8000"
        assert config["server"]["api_key"] == "sk-mykey"
        assert config["llm"]["model"] == "gpt-4o"
        assert config["local_llm"]["enabled"] is False

def test_node_setup_command_local():
    with runner.isolated_filesystem():
        # Input: server_url, api_key, local? (y), port
        input_str = "http://myserver:8000\nsk-mykey\ny\n11434\n"
        result = runner.invoke(app, ["setup"], input=input_str)

        assert result.exit_code == 0

        with open("node_config.toml", "rb") as f:
            import tomli
            config = tomli.load(f)

        assert config["local_llm"]["enabled"] is True
        assert config["local_llm"]["port"] == 11434

@patch("openbeepboop.cli.node.load_node_config")
@patch("openbeepboop.cli.node.NodeClient")
def test_node_run_command(mock_client_cls, mock_load_config):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_load_config.return_value = MagicMock()

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    mock_client.run_loop.assert_called_once()

@patch("openbeepboop.cli.node.load_node_config")
@patch("openbeepboop.cli.node.NodeClient")
def test_node_batch_command(mock_client_cls, mock_load_config):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_load_config.return_value = MagicMock()

    # Mock run_once to return 1 job then 0 jobs to break loop
    mock_client.run_once.side_effect = [1, 0]

    result = runner.invoke(app, ["batch"])
    assert result.exit_code == 0
    assert mock_client.run_once.call_count == 2

def test_node_run_missing_config():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["run"]) # Default config missing
        assert result.exit_code == 1
        assert "Error loading config" in result.stdout

def test_node_batch_missing_config():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["batch"]) # Default config missing
        assert result.exit_code == 1
        assert "Error loading config" in result.stdout
