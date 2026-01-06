import pytest
from openbeepboop.common.config import load_node_config, NodeConfig
import os
import tempfile
import tomli_w

def test_load_node_config_success():
    config_data = {
        "server": {"url": "http://test", "api_key": "sk-test"},
        "llm": {"model": "gpt-test"},
        "local_llm": {"enabled": False, "port": 11434}
    }
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        tomli_w.dump(config_data, f)
        path = f.name

    try:
        config = load_node_config(path)
        assert isinstance(config, NodeConfig)
        assert config.server.url == "http://test"
        assert config.llm.model == "gpt-test"
    finally:
        os.remove(path)

def test_load_node_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_node_config("non_existent_file.toml")

def test_load_node_config_invalid_format():
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(b"invalid toml [")
        path = f.name

    try:
        # Depending on toml lib, it might raise different errors, but usually pydantic validation or toml decode error
        # Here we just check it fails
        with pytest.raises(Exception):
            load_node_config(path)
    finally:
        os.remove(path)
