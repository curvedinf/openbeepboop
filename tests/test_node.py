import pytest
from openbeepboop.node.worker import NodeClient, NodeConfig
from openbeepboop.common.config import ServerConfig, LLMConfig, LocalLLMConfig
from openbeepboop.common.models import JobStatus
from unittest.mock import MagicMock, patch

@pytest.fixture
def node_config():
    return NodeConfig(
        server=ServerConfig(url="http://testserver", api_key="sk-test"),
        llm=LLMConfig(model="gpt-test"),
        local_llm=LocalLLMConfig(enabled=False)
    )

def test_node_client_fetch_jobs(node_config):
    client = NodeClient(node_config)
    client.client.post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: [{"id": "1", "request_payload": {}}]))

    jobs = client.fetch_jobs(limit=1)
    assert len(jobs) == 1
    assert jobs[0]["id"] == "1"
    client.client.post.assert_called_with("/internal/queue/fetch", json={"limit": 1}, headers=client.headers)

@patch("openbeepboop.node.worker.completion")
def test_node_process_job_remote(mock_completion, node_config):
    client = NodeClient(node_config)

    job = {
        "id": "job-1",
        "request_payload": {
            "model": "gpt-user",
            "messages": [{"role": "user", "content": "hi"}]
        }
    }

    mock_response = MagicMock()
    mock_response.model_dump.return_value = {"id": "chatcmpl-1", "choices": []}
    mock_completion.return_value = mock_response

    result = client.process_job(job)

    assert result["id"] == "job-1"
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["result"]["id"] == "chatcmpl-1"

    # Check if correct args passed to litellm
    # Payload model should be used if not overridden?
    # In my code: kwargs = payload excluding messages.
    # payload has "model": "gpt-user".
    # config has "model": "gpt-test".
    # I wrote: if "model" not in kwargs: kwargs["model"] = self.config.llm.model
    # So "gpt-user" should be used.

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["model"] == "gpt-user"
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]

@patch("openbeepboop.node.worker.completion")
def test_node_process_job_local_override(mock_completion):
    config = NodeConfig(
        server=ServerConfig(),
        llm=LLMConfig(),
        local_llm=LocalLLMConfig(enabled=True, port=1234)
    )
    client = NodeClient(config)

    job = {
        "id": "job-1",
        "request_payload": {
            "model": "gpt-user",
            "messages": []
        }
    }

    mock_response = MagicMock()
    mock_response.model_dump.return_value = {}
    mock_completion.return_value = mock_response

    client.process_job(job)

    kwargs = mock_completion.call_args.kwargs
    assert kwargs["api_base"] == "http://localhost:1234/v1"
    # assert kwargs["model"] == ... # It might still be gpt-user or overridden depending on logic.
    # Current logic: `kwargs["model"] = "openai/gpt-user"` if we forced it? No.
    # Current logic: we only inject api_base and api_key.
    # The payload model is passed through.
    assert "messages" in kwargs

@patch("openbeepboop.node.worker.completion")
def test_node_process_job_failure(mock_completion, node_config):
    client = NodeClient(node_config)
    mock_completion.side_effect = Exception("LiteLLM Error")

    job = {"id": "job-1", "request_payload": {"messages": []}}

    result = client.process_job(job)
    assert result["status"] == JobStatus.FAILED.value
    assert "LiteLLM Error" in result["error"]

def test_submit_results(node_config):
    client = NodeClient(node_config)
    client.client.post = MagicMock()

    results = [{"id": "1", "status": "COMPLETED"}]
    client.submit_results(results)

    client.client.post.assert_called_with("/internal/queue/submit", json=results, headers=client.headers)
