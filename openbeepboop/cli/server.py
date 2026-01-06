import typer
import uvicorn
import secrets
from openbeepboop.common.db import init_db, get_db_path
import os
import sqlite3

app = typer.Typer()

@app.command()
def start(host: str = "0.0.0.0", port: int = 8000):
    """Start the OpenBeepBoop Queue Server."""
    typer.echo(f"Starting server on {host}:{port}")
    uvicorn.run("openbeepboop.server.api:app", host=host, port=port, reload=False)

@app.command()
def setup():
    """Interactive wizard to setup the server."""
    typer.echo("OpenBeepBoop Server Setup")

    default_db_path = get_db_path()
    db_path = typer.prompt("Where should the database be stored?", default=default_db_path)

    init_db(db_path)
    typer.echo(f"Database initialized at {db_path}")

    # Generate Admin Key
    admin_key = f"sk-{secrets.token_hex(16)}"

    # Store key
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # In real app, we hash the key. For now, let's just store it or hash it simply.
    # SPEC: "Generates an Admin API Key."
    # Let's store it as is for simplicity of this prototype, or mock hash.
    # The SPEC schema has `key_hash`.

    import hashlib
    key_hash = hashlib.sha256(admin_key.encode()).hexdigest()

    try:
        cursor.execute("INSERT INTO api_keys (key_hash, name, role) VALUES (?, ?, ?)", (key_hash, "Admin", "ADMIN"))
        conn.commit()
    except sqlite3.IntegrityError:
        typer.echo("Admin key already exists (or collision).")
    finally:
        conn.close()

    typer.echo(f"Setup complete. Your Admin Key is: {admin_key}")
    typer.echo("Run server with `openbeepboop-server start`")

if __name__ == "__main__":
    app()
