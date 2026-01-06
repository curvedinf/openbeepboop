from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import os

try:
    import tomllib
except ImportError:
    import tomli as tomllib

class ServerConfig(BaseModel):
    url: str = "http://localhost:8000"
    api_key: Optional[str] = None

class LocalLLMConfig(BaseModel):
    enabled: bool = False
    port: int = 11434

class LLMConfig(BaseModel):
    model: Optional[str] = None
    api_key: Optional[str] = None

class NodeConfig(BaseModel):
    server: ServerConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    local_llm: LocalLLMConfig = Field(default_factory=LocalLLMConfig)

def load_node_config(path: str = "node_config.toml") -> NodeConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found at {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return NodeConfig(**data)
