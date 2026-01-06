# OpenBeepBoop

OpenBeepBoop is a distributed, offline-first batch LLM inference orchestration system.

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

## Usage

### Server

```bash
openbeepboop-server setup
openbeepboop-server start
```

### Node

```bash
openbeepboop-node setup
openbeepboop-node run
```

### Client

```python
from openbeepboop import Client

client = Client(base_url="http://localhost:8000")
job = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(job.get(wait=True))
```
