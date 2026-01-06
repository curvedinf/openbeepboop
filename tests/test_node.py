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

def test_node_client_fetch_jobs_error(node_config):
    client = NodeClient(node_config)
    client.client.post = MagicMock(side_effect=Exception("Connection error"))

    jobs = client.fetch_jobs(limit=1)
    assert jobs == []

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

def test_submit_results_error(node_config):
    client = NodeClient(node_config)
    client.client.post = MagicMock(side_effect=Exception("Post error"))

    # Should log error but not raise
    results = [{"id": "1", "status": "COMPLETED"}]
    client.submit_results(results)

def test_submit_results_empty(node_config):
    client = NodeClient(node_config)
    client.client.post = MagicMock()

    client.submit_results([])
    client.client.post.assert_not_called()

def test_run_once(node_config):
    client = NodeClient(node_config)
    client.fetch_jobs = MagicMock(return_value=[{"id": "j1"}])
    client.process_job = MagicMock(return_value={"id": "j1", "status": "COMPLETED"})
    client.submit_results = MagicMock()

    count = client.run_once()
    assert count == 1
    client.process_job.assert_called_once()
    client.submit_results.assert_called_once()

@patch("openbeepboop.node.worker.time.sleep")
def test_run_loop(mock_sleep, node_config):
    client = NodeClient(node_config)

    # Side effect to break the loop after 2 calls
    # 1. returns 0 jobs -> sleep
    # 2. returns 1 job -> process
    # 3. raise exception to exit loop for test
    client.run_once = MagicMock(side_effect=[0, 1, KeyboardInterrupt])

    try:
        client.run_loop()
    except KeyboardInterrupt:
        pass

    mock_sleep.assert_called_once_with(5)
    assert client.run_once.call_count == 3
