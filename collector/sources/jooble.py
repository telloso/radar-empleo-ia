"""Jooble REST API (job aggregator; we use it for jobs in Madrid).

Needs a free API key in JOOBLE_API_KEY. The key was issued on es.jooble.org,
so requests must go to that domain (jooble.org answers 403).
https://es.jooble.org/api/about
"""

import html
import logging
import os
import re

from http_utils import FetchError, post_json
from models import Job

logger = logging.getLogger(__name__)

API_URL = "https://es.jooble.org/api/{key}"
SOURCE = "jooble"
TAG = re.compile(r"<[^>]+>")


def fetch_jobs(search: str, location: str = "Madrid") -> list[Job]:
    """Return the first page of Jooble jobs matching `search` in `location`."""
    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        raise FetchError("JOOBLE_API_KEY is not set")

    data = post_json(
        API_URL.format(key=api_key),
        body={"keywords": search, "location": location},
        secret=api_key,
    )

    jobs = []
    for raw in data.get("jobs", []):
        try:
            jobs.append(_to_job(raw))
        except KeyError as exc:
            logger.warning("Skipping Jooble job without field %s", exc)
    return jobs


def _to_job(raw: dict) -> Job:
    """Translate one Jooble job into our common Job shape."""
    return Job(
        source=SOURCE,
        external_id=str(raw["id"]),
        title=raw["title"],
        company=raw.get("company") or "Unknown",
        location=raw.get("location") or "",
        url=raw["link"],
        published_at=raw.get("updated", ""),
        salary=raw.get("salary") or None,
        description=_clean(raw.get("snippet", "")),
    )


def _clean(snippet: str) -> str:
    """Turn Jooble's HTML snippet ('&nbsp;...<b>Python</b>') into plain text."""
    text = html.unescape(TAG.sub("", snippet))
    return " ".join(text.split())
