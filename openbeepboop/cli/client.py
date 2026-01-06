import typer
import json
import os
from typing import Optional
from openbeepboop.client import Client

app = typer.Typer()

def get_client(server_url: str, api_key: Optional[str]) -> Client:
    return Client(base_url=server_url, api_key=api_key)

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
    job_id: str = typer.Argument(..., help="The Job ID to poll"),
    server_url: str = typer.Option("http://localhost:8000", help="Queue Server URL"),
    api_key: Optional[str] = typer.Option(None, envvar="OPENBEEPBOOP_API_KEY", help="API Key"),
    wait: bool = typer.Option(False, help="Block until the job is complete")
):
    """
    Poll the status of a job.
    """
    client = get_client(server_url, api_key)
    try:
        # We need to construct a JobHandle manually or just use the polling method directly.
        # The Client.jobs.poll returns a list of JobHandles.
        jobs = client.jobs.poll([job_id])
        if not jobs:
            typer.echo(f"Job {job_id} not found.", err=True)
            raise typer.Exit(code=1)

        job = jobs[0]

        if wait and not job.is_completed:
             typer.echo("Waiting for result...")
             result = job.get(wait=True)
             typer.echo(json.dumps(result, indent=2))
        else:
             typer.echo(f"Status: {job.status}")
             if job.is_completed:
                 typer.echo("Result:")
                 typer.echo(json.dumps(job.result, indent=2))

    except Exception as e:
        typer.echo(f"Error polling job: {e}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
