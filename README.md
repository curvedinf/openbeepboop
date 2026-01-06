# OpenBeepBoop

OpenBeepBoop is a distributed, offline-first batch LLM inference orchestration system. It is designed to decouple request submission from inference execution, allowing for scalable, pull-based processing using heterogeneous compute nodes.

## Project Goals

*   **Distributed Architecture**: Decouple the client submitting requests from the nodes executing them.
*   **Offline-First**: Support batch processing where the client doesn't need to stay connected.
*   **Scalable**: Easily add more Node Clients to increase throughput.
*   **Heterogeneous Compute**: Use a mix of local GPUs (via Ollama, LM Studio) and remote APIs.

## Project Overview

OpenBeepBoop consists of three main components:

1.  **Queue Server**: A lightweight HTTP server backed by SQLite that acts as the central coordinator.
2.  **Node Client**: A worker that pulls requests, runs inference (using LiteLLM), and pushes results back.
3.  **User Library**: A Python client for easily submitting jobs and retrieving results.

### Key Features
*   **Easy Installation**: `pip install openbeepboop`
*   **Async API**: Submit now, retrieve later.
*   **Flexible Deployment**: Run nodes as daemons or cron jobs.
*   **Simple Configuration**: TOML-based config with interactive setup wizards.

## Architecture

```mermaid
flowchart LR
    User[User Script / App] -- "Python Lib / HTTP" --> Server[Queue Server]
    Server -- "SQLite" --> DB[(Database)]

    Node1[Node Client 1] -- "Pull Jobs / Push Results" --> Server
    Node2[Node Client 2] -- "Pull Jobs / Push Results" --> Server

    Node1 -- "LiteLLM" --> LLM1[Local/Remote LLM]
    Node2 -- "LiteLLM" --> LLM2[Local/Remote LLM]
```

## Data Flow

```mermaid
sequenceDiagram
    participant U as User Client
    participant S as Queue Server
    participant N as Node Client
    participant L as LLM

    U->>S: POST /v1/chat/completions (Job Submit)
    S-->>U: 202 Accepted (Job ID)

    loop Fetch Loop
        N->>S: POST /internal/queue/fetch
        alt Jobs Available
            S-->>N: Job Data
            N->>L: Inference Request
            L-->>N: Inference Result
            N->>S: POST /internal/queue/submit (Result)
        else No Jobs
            S-->>N: Empty List
        end
    end

    loop Poll Loop
        U->>S: POST /v1/results/poll (Job ID)
        alt Completed
            S-->>U: Job Result
        else Queued/Processing
            S-->>U: Status
        end
    end
```

## Installation

```bash
pip install openbeepboop
```

## Basic Operation

The typical workflow involves setting up the server, configuring one or more nodes, and then using the Python client to submit jobs.

### 1. Server Setup

Start by setting up and running the Queue Server.

```bash
# Initialize configuration and database
openbeepboop-server setup

# Start the server (default port 8000)
openbeepboop-server start
```

### 2. Node Setup

On any machine with compute resources (or access to LLM APIs):

```bash
# Configure the node (connect to server, define model)
openbeepboop-node setup

# Run the node in daemon mode
openbeepboop-node run
```

### 3. Basic Use Case

Here is how you can submit a job from your Python script:

```python
from openbeepboop import Client

# Initialize client (point to your server)
client = Client(base_url="http://localhost:8000")

# Submit a job (returns immediately)
job = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}]
)
print(f"Job submitted with ID: {job.id}")

# Wait for result (blocking)
# In a real app, you might poll later instead of waiting
result = job.get(wait=True)
print("Result:", result.choices[0].message.content)
```

## CLI Commands

### Server CLI (`openbeepboop-server`)

*   `setup`: Interactive wizard to generate initial API key and database.
*   `start [--port <port>] [--host <host>]`: Start the server.

### Node CLI (`openbeepboop-node`)

*   `setup`: Interactive wizard to create `node_config.toml`.
*   `run`: Runs the node in a continuous loop (daemon mode).
*   `batch`: Runs once, processes available queue items, then exits (useful for Cron).

### Client CLI (`openbeepboop-client`)

You can also use the CLI to interact with the queue directly.

*   `submit "Prompt text" [--model <model>] [--wait]`: Submit a job.
    *   Example: `openbeepboop-client submit "Hello world" --wait`
*   `poll <job_id> [--wait]`: Poll for job status and result.
    *   Example: `openbeepboop-client poll job-uuid-1234 --wait`
