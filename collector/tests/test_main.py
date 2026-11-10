"""Tests for the collector loop: searches are parsed and run, failures are contained.

The sources and the database are fakes, so nothing touches the network or Postgres.
"""

from unittest import mock

import pytest

import main
from http_utils import FetchError


@pytest.fixture
def save_jobs(monkeypatch):
    """Replace db.save_jobs; by default every job it gets counts as new."""
    fake = mock.Mock(side_effect=lambda conn, jobs: len(jobs))
    monkeypatch.setattr(main.db, "save_jobs", fake)
    return fake


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ["python"]),
        ("", ["python"]),
        ("python", ["python"]),
        (" python , devops ,, python", ["python", "devops"]),
        ("inteligencia artificial,automatización", ["inteligencia artificial", "automatización"]),
    ],
)
def test_parse_searches(value, expected):
    assert main.parse_searches(value) == expected


def test_collect_runs_every_search(save_jobs):
    fetch_jobs = mock.Mock(side_effect=[["a", "b"], ["c"]])

    assert main.collect("conn", "jooble", fetch_jobs, ["python", "devops"]) is True
    assert fetch_jobs.call_args_list == [mock.call("python"), mock.call("devops")]
    assert save_jobs.call_count == 2


def test_collect_stops_the_source_after_a_failure(save_jobs):
    fetch_jobs = mock.Mock(side_effect=[["a"], FetchError("429"), ["never"]])

    assert main.collect("conn", "jooble", fetch_jobs, ["python", "devops", "n8n"]) is False
    # The first search was saved; after the error, 'n8n' was never requested.
    assert fetch_jobs.call_count == 2
    save_jobs.assert_called_once_with("conn", ["a"])
