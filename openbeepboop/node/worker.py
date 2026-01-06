import time
import asyncio
import httpx
import logging
from litellm import completion
from openbeepboop.common.config import NodeConfig, load_node_config
from openbeepboop.common.models import JobStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node")

class NodeClient:
    def __init__(self, config: NodeConfig):
        self.config = config
        self.client = httpx.Client(base_url=config.server.url, timeout=30.0)
        self.headers = {"Authorization": f"Bearer {config.server.api_key}"}

    def fetch_jobs(self, limit: int = 1):
        try:
            resp = self.client.post("/internal/queue/fetch", json={"limit": limit}, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}")
            return []

    def process_job(self, job):
        logger.info(f"Processing job {job['id']}")
        request_payload = job["request_payload"]

        # Determine model and api_base
        model = self.config.llm.model
        api_base = None
        api_key = self.config.llm.api_key

        if self.config.local_llm.enabled:
            # Construct simplified local LLM config
            # Assuming OpenAI compatible local server (like Ollama, LM Studio)
            model = model or "openai/local-model" # LiteLLM needs a model name, usually 'openai/<something>' for generic openai compatible
            if not model.startswith("openai/"):
                 model = f"openai/{model}" if model else "openai/local"

            api_base = f"http://localhost:{self.config.local_llm.port}/v1"
            api_key = api_key or "sk-dummy" # Local servers often don't check key

        # Override with payload model if needed, or enforce node config?
        # Usually node enforcing model is safer for "heterogeneous compute nodes" specializing in models.
        # But payload usually has "model" field.
        # Let's check SPEC. "If local_llm.enabled is true... overrides 'llm.model' logic".
        # It also says "Use LiteLLM to invoke the model."

        # If the user payload specifies a model, do we use it?
        # SPEC says: "LiteLLM (supporting local and remote models)"
        # And "Node Client... pulls requests... runs inference".
        # If I have a node for "gpt-4" and another for "llama3", the fetch might need to filter?
        # The SPEC fetch endpoint doesn't support filtering by model.
        # So assumes any node can handle any job, OR the node overrides the model.
        # "If local_llm.enabled is true, overrides 'llm.model' logic to point to local instance"

        # If payload has 'model', LiteLLM uses it.
        # If we want to force the node's local model, we might need to overwrite `request_payload['model']`.

        if self.config.local_llm.enabled:
             # Force usage of local endpoint
             # We might need to map the model name or just pass it through if the local server supports it.
             # But `api_base` is crucial.
             pass

        try:
            # Prepare args for litellm
            # We pass the whole payload as kwargs?
            # request_payload follows OpenAI ChatCompletion schema

            # extract messages
            messages = request_payload.get("messages")
            # extract other params
            kwargs = {k:v for k,v in request_payload.items() if k != "messages"}

            # If local, we inject api_base
            if self.config.local_llm.enabled:
                kwargs["api_base"] = api_base
                kwargs["api_key"] = api_key
                # We might overwrite model if needed, but usually local server ignores it or matches it.
                # If we want to strictly use the node's configured model:
                # kwargs["model"] = "openai/custom"
                # But let's leave it to LiteLLM or payload if possible.
            elif api_key:
                 kwargs["api_key"] = api_key

            # If the node config specifies a model, we might want to default to it if payload doesn't have one?
            # Or override? "If local_llm... overrides 'llm.model' logic".

            if self.config.llm.model and not self.config.local_llm.enabled:
                 # If node is configured for specific remote model
                 # We might want to use that.
                 # But payload `model` usually takes precedence in `completion`.
                 # Let's assume payload is correct, or if missing use config.
                 if "model" not in kwargs:
                     kwargs["model"] = self.config.llm.model

            response = completion(messages=messages, **kwargs)

            # Response is a ModelResponse object (pydantic-like or dict-like)
            # We need to serialize it.
            return {
                "id": job["id"],
                "status": JobStatus.COMPLETED.value,
                "result": response.model_dump() if hasattr(response, 'model_dump') else dict(response)
            }

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return {
                "id": job["id"],
                "status": JobStatus.FAILED.value,
                "error": str(e)
            }

    def submit_results(self, results):
        if not results:
            return
        try:
            self.client.post("/internal/queue/submit", json=results, headers=self.headers)
        except Exception as e:
            logger.error(f"Error submitting results: {e}")

    def run_once(self):
        jobs = self.fetch_jobs(limit=1) # One at a time for simplicity or configurable
        results = []
        for job in jobs:
            res = self.process_job(job)
            results.append(res)
        self.submit_results(results)
        return len(jobs)

    def run_loop(self):
        logger.info("Starting node loop...")
        while True:
            count = self.run_once()
            if count == 0:
                time.sleep(5) # Sleep if no jobs
