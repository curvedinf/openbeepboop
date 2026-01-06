import pytest
from openbeepboop.client.client import Client
from unittest.mock import MagicMock

def test_client_chat_completion_create():
    c = Client(base_url="http://test")
    c.http_client.post = MagicMock(return_value=MagicMock(status_code=202, json=lambda: {"id": "job-1", "status": "QUEUED"}))

    handle = c.chat.completions.create(model="test", messages=[])

    assert handle.id == "job-1"
    assert handle.status == "QUEUED"
    c.http_client.post.assert_called_with("/v1/chat/completions", json={"model": "test", "messages": []})

def test_client_job_poll():
    c = Client(base_url="http://test")

    # Mock polling response
    mock_resp = {
        "jobs": [
            {"id": "job-1", "status": "COMPLETED", "result": {"foo": "bar"}}
        ]
    }
    c.http_client.post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: mock_resp))

    handles = c.jobs.poll(["job-1"])
    assert len(handles) == 1
    assert handles[0].status == "COMPLETED"
    assert handles[0].result == {"foo": "bar"}

def test_job_handle_get_wait():
    c = Client(base_url="http://test")

    # We need to simulate the sequence of API calls.
    # 1. create -> returns job id
    # 2. poll -> returns queued
    # 3. poll -> returns completed

    poll_responses = iter([
         {"jobs": [{"id": "job-1", "status": "QUEUED", "result": None}]},
         {"jobs": [{"id": "job-1", "status": "COMPLETED", "result": {"done": True}}]}
    ])

    def side_effect(path, json=None):
        if path == "/v1/chat/completions":
            return MagicMock(status_code=202, json=lambda: {"id": "job-1", "status": "QUEUED"})
        if path == "/v1/results/poll":
            return MagicMock(status_code=200, json=lambda: next(poll_responses))
        return MagicMock(status_code=404)

    c.http_client.post = MagicMock(side_effect=side_effect)

    handle = c.chat.completions.create(model="t", messages=[])

    # get(wait=True)
    result = handle.get(wait=True)
    assert result == {"done": True}
