import typer
import json
import os
import tomli_w
from typing import Optional, List
from openbeepboop.client import Client
from openbeepboop.common.config import load_client_config

app = typer.Typer()

def get_client(server_url: Optional[str] = None, api_key: Optional[str] = None) -> Client:
    # Defaults
    final_url = "http://localhost:8000"
    final_key = None

    # Try to load from config
    try:
        config = load_client_config()
        final_url = config.server.url
        final_key = config.server.api_key
    except FileNotFoundError:
        pass

    # Overrides
    if server_url and server_url != "http://localhost:8000":
        final_url = server_url
    if api_key:
        final_key = api_key

    return Client(base_url=final_url, api_key=final_key)

@app.command()
def setup():
    """Interactive wizard to create client_config.toml."""
    typer.echo("OpenBeepBoop Client Setup")

    server_url = typer.prompt("Enter Queue Server URL", default="http://localhost:8000")
    api_key = typer.prompt("Enter API Key (optional)", default="", show_default=False)

    server_config = {"url": server_url}
    if api_key:
        server_config["api_key"] = api_key

    config = {
        "server": server_config
    }

    with open("client_config.toml", "wb") as f:
        tomli_w.dump(config, f)

    typer.echo("client_config.toml created.")

@app.command()
def submit(
    prompt: str = typer.Argument(..., help="The prompt to send to the LLM"),
    model: str = typer.Option("gpt-3.5-turbo", help="The model to use"),
    server_url: str = typer.Option("http://localhost:8000", help="Queue Server URL"),
    api_key: Optional[str] = typer.Option(None, envvar="OPENBEEPBOOP_API_KEY", help="API Key"),
    wait: bool = typer.Option(False, help="Wait for the result immediately")
):
    """
    Submit a new inference job to the queue.
    """
    client = get_client(server_url, api_key)
    try:
        job = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        typer.echo(f"Job submitted successfully. ID: {job.id}")

        if wait:
            typer.echo("Waiting for result...")
            result = job.get(wait=True)
            if result:
                 typer.echo(json.dumps(result, indent=2))
            else:
                 typer.echo("Job finished but no result returned (possible error).")

    except Exception as e:
        typer.echo(f"Error submitting job: {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def poll(
    job_ids: List[str] = typer.Argument(..., help="One or more Job IDs to poll"),
    server_url: str = typer.Option("http://localhost:8000", help="Queue Server URL"),
    api_key: Optional[str] = typer.Option(None, envvar="OPENBEEPBOOP_API_KEY", help="API Key"),
    wait: bool = typer.Option(False, help="Block until the job(s) are complete (only for first job if multiple)")
):
    """
    Poll the status of one or more jobs.
    """
    client = get_client(server_url, api_key)
    try:
        if not job_ids:
            typer.echo("No job IDs provided.", err=True)
            raise typer.Exit(code=1)

        # Batch poll
        jobs = client.jobs.poll(job_ids)
        if not jobs:
            typer.echo(f"No jobs found for IDs: {job_ids}", err=True)
            raise typer.Exit(code=1)

        # Mapping for output
        results = []

        for job in jobs:
            job_data = {
                "id": job.id,
                "status": job.status,
                "completed": job.is_completed
            }
            if job.is_completed:
                job_data["result"] = job.result
            results.append(job_data)

        # If waiting is requested
        if wait:
             # Logic for waiting on multiple jobs is complex via CLI flags.
             # For simplicity, we only wait on the FIRST job if multiple are passed,
             # or we could iterate. Let's iterate but warn.

             if len(job_ids) > 1:
                 typer.echo("Warning: --wait flag specified with multiple jobs. Waiting for each sequentially.")

             final_results = []
             for job in jobs:
                 if not job.is_completed:
                     typer.echo(f"Waiting for job {job.id}...")
                     res = job.get(wait=True)
                     final_results.append({
                         "id": job.id,
                         "status": "COMPLETED", # It finished after wait
                         "completed": True,
                         "result": res
                     })
                 else:
                     # Already done
                     final_results.append({
                         "id": job.id,
                         "status": job.status,
                         "completed": True,
                         "result": job.result
                     })

             typer.echo(json.dumps(final_results, indent=2))

        else:
            # Immediate output
            if len(results) == 1:
                 # Maintain backward compatible single-object output if user only asked for one?
                 # Or consistent list output?
                 # If we change to always list, it might break scripts expecting single object.
                 # But standardizing on List is safer for "poll <ids>" command.
                 # HOWEVER, the previous implementation printed specific text lines.
                 # Let's try to be helpful.

                 job = jobs[0]
                 typer.echo(f"Status: {job.status}")
                 if job.is_completed:
                     typer.echo("Result:")
                     typer.echo(json.dumps(job.result, indent=2))
            else:
                # Multiple jobs, output JSON list
                typer.echo(json.dumps(results, indent=2))

    except Exception as e:
        typer.echo(f"Error polling job: {e}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
