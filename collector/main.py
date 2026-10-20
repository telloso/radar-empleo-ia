"""Job collector: fetches offers from the configured sources and prints a summary."""

import logging
import os
import sys

from http_utils import FetchError
from sources import remotive

logger = logging.getLogger("collector")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    search = os.getenv("COLLECTOR_SEARCH", "python")

    try:
        jobs = remotive.fetch_jobs(search)
    except FetchError as exc:
        logger.error("Remotive failed: %s", exc)
        return 1

    logger.info("Remotive: %d jobs for '%s'", len(jobs), search)
    for job in jobs[:5]:
        print(f"- {job.title} | {job.company} | {job.location} | {job.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
