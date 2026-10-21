"""Job collector: fetches offers from the configured sources and prints a summary."""

import logging
import os
import sys

from http_utils import FetchError
from sources import jooble, remotive

logger = logging.getLogger("collector")

SOURCES = {
    "remotive": remotive.fetch_jobs,
    "jooble": jooble.fetch_jobs,
}


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    search = os.getenv("COLLECTOR_SEARCH", "python")

    failed = []
    for name, fetch_jobs in SOURCES.items():
        # One broken source must not stop the others.
        try:
            jobs = fetch_jobs(search)
        except FetchError as exc:
            logger.error("%s failed: %s", name, exc)
            failed.append(name)
            continue

        logger.info("%s: %d jobs for '%s'", name, len(jobs), search)
        for job in jobs[:5]:
            print(f"- {job.title} | {job.company} | {job.location} | {job.url}")

    # Non-zero exit code so whoever runs us (Docker, n8n) can tell something broke.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
