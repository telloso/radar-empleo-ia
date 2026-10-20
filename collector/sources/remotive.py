"""Remotive public API (remote jobs, no API key).

Terms: at most ~4 requests a day and 2 per minute, and every job shown must
link back to Remotive as its source.
https://github.com/remotive-io/remote-jobs-api
"""

import logging

from http_utils import get_json
from models import Job

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
SOURCE = "remotive"


def fetch_jobs(search: str, limit: int = 50) -> list[Job]:
    """Return up to `limit` Remotive jobs matching `search`."""
    data = get_json(API_URL, params={"search": search, "limit": limit})

    jobs = []
    for raw in data.get("jobs", []):
        try:
            jobs.append(_to_job(raw))
        except KeyError as exc:
            logger.warning("Skipping Remotive job without field %s", exc)
    return jobs


def _to_job(raw: dict) -> Job:
    """Translate one Remotive job into our common Job shape."""
    return Job(
        source=SOURCE,
        external_id=str(raw["id"]),
        title=raw["title"],
        company=raw["company_name"],
        location=raw.get("candidate_required_location") or "Remote",
        url=raw["url"],
        published_at=raw["publication_date"],
        salary=raw.get("salary") or None,
        description=raw.get("description", ""),
    )
