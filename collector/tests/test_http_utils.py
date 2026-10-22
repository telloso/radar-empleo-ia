"""Tests for the HTTP helper, with requests and time.sleep mocked out.

No test touches the network or really waits for the backoff.
"""

from unittest import mock

import pytest
import requests

import http_utils
from http_utils import FetchError, get_json, post_json


def fake_response(status: int, body: dict | None = None) -> mock.Mock:
    """A stand-in for requests.Response with just what get_json uses."""
    response = mock.Mock(status_code=status, ok=status < 400, headers={})
    response.json.return_value = body
    return response


@pytest.fixture
def fake_request(monkeypatch):
    """Replace requests.request and time.sleep; return the request mock."""
    request = mock.Mock()
    monkeypatch.setattr(http_utils.requests, "request", request)
    monkeypatch.setattr(http_utils.time, "sleep", mock.Mock())
    return request


def test_returns_json_on_success(fake_request):
    fake_request.return_value = fake_response(200, {"jobs": []})

    assert get_json("https://example.com") == {"jobs": []}
    assert fake_request.call_count == 1


def test_retries_server_error_then_succeeds(fake_request):
    fake_request.side_effect = [fake_response(503), fake_response(200, {"jobs": [1]})]

    assert get_json("https://example.com") == {"jobs": [1]}
    assert fake_request.call_count == 2


def test_fails_fast_on_client_error(fake_request):
    fake_request.return_value = fake_response(401)

    with pytest.raises(FetchError, match="HTTP 401"):
        get_json("https://example.com")
    assert fake_request.call_count == 1  # retrying a 401 would not help


def test_gives_up_after_max_retries(fake_request):
    fake_request.side_effect = requests.ConnectionError("connection refused")

    with pytest.raises(FetchError, match="after 3 attempts"):
        get_json("https://example.com", max_retries=3)
    assert fake_request.call_count == 3


def test_secret_is_hidden_in_errors(fake_request):
    fake_request.return_value = fake_response(403)

    with pytest.raises(FetchError) as error:
        post_json("https://api.example.com/SECRET123", body={}, secret="SECRET123")
    assert "SECRET123" not in str(error.value)
    assert "***" in str(error.value)
