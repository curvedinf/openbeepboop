import httpx
import time
from typing import List, Dict, Any, Optional
from openbeepboop.common.models import JobStatus

class JobHandle:
    def __init__(self, client, job_id: str, status: str = JobStatus.QUEUED.value):
        self.client = client
        self.id = job_id
        self._status = status
        self._result = None
        self._last_poll = 0

    @property
    def status(self):
        return self._status

    @property
    def result(self):
        return self._result

    @property
    def is_completed(self):
        return self._status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]

    def get(self, wait: bool = True, timeout: int = 60) -> Optional[Dict[str, Any]]:
        if self.is_completed and self._result:
            return self._result

        start_time = time.time()
        while True:
            # Poll
            updated_jobs = self.client.jobs.poll([self.id])
            if updated_jobs:
                updated_job = updated_jobs[0]
                self._status = updated_job.status
                self._result = updated_job.result

                if self.is_completed:
                    return self._result

            if not wait:
                return None

            if time.time() - start_time > timeout:
                raise TimeoutError(f"Job {self.id} timed out after {timeout} seconds")

            time.sleep(1)

class CompletionsClient:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs) -> JobHandle:
        """
        Submit a chat completion job.
        Accepts standard OpenAI parameters (model, messages, etc.)
        """
        resp = self.client._post("/v1/chat/completions", json=kwargs)
        data = resp.json()
        return JobHandle(self.client, data["id"], data["status"])

class ChatClient:
    def __init__(self, client):
        self.completions = CompletionsClient(client)

class JobsClient:
    def __init__(self, client):
        self.client = client

    def poll(self, ids: List[str]) -> List[JobHandle]:
        resp = self.client._post("/v1/results/poll", json={"ids": ids})
        data = resp.json()

        handles = []
        for j in data["jobs"]:
            handle = JobHandle(self.client, j["id"], j["status"])
            handle._result = j.get("result")
            handles.append(handle)
        return handles

class Client:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.http_client = httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30.0)

        self.chat = ChatClient(self)
        self.jobs = JobsClient(self)

    def _post(self, path: str, json: Dict[str, Any]) -> httpx.Response:
        resp = self.http_client.post(path, json=json)
        resp.raise_for_status()
        return resp
