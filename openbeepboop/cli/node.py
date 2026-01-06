import typer
import tomli_w
import os
from openbeepboop.node.worker import NodeClient, load_node_config

app = typer.Typer()

@app.command()
def run(config: str = "node_config.toml"):
    """Run the node in continuous loop mode."""
    try:
        node_config = load_node_config(config)
    except Exception as e:
        typer.echo(f"Error loading config: {e}")
        raise typer.Exit(1)

    client = NodeClient(node_config)
    client.run_loop()

@app.command()
def batch(config: str = "node_config.toml"):
    """Run the node once (process available queue then exit)."""
    try:
        node_config = load_node_config(config)
    except Exception as e:
        typer.echo(f"Error loading config: {e}")
        raise typer.Exit(1)

    client = NodeClient(node_config)
    # SPEC: "Runs once, processes available queue, then exits"
    # We loop until no jobs are returned?
    while True:
        count = client.run_once()
        if count == 0:
            break

@app.command()
def setup():
    """Interactive wizard to create node_config.toml."""
    typer.echo("OpenBeepBoop Node Setup")

    server_url = typer.prompt("Enter Queue Server URL", default="http://localhost:8000")
    api_key = typer.prompt("Enter Node API Key")

    local = typer.confirm("Are you using a local LLM server?", default=False)

    config = {
        "server": {
            "url": server_url,
            "api_key": api_key
        },
        "llm": {},
        "local_llm": {
            "enabled": False,
            "port": 11434
        }
    }

    if local:
        port = typer.prompt("Which port?", default=11434, type=int)
        config["local_llm"]["enabled"] = True
        config["local_llm"]["port"] = port
    else:
        model = typer.prompt("Enter LiteLLM model name (e.g. gpt-4)")
        config["llm"]["model"] = model

    with open("node_config.toml", "wb") as f:
        tomli_w.dump(config, f)

    typer.echo("node_config.toml created.")

if __name__ == "__main__":
    app()
