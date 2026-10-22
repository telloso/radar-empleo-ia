"""Job collector: fetches offers from the configured sources and saves them in PostgreSQL."""

import logging
import os
import sys

import psycopg

import db
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

    try:
        conn = db.connect()
    except psycopg.OperationalError as exc:
        # Without the database there is nowhere to save, so don't spend API requests.
        logger.error("cannot connect to the database: %s", exc)
        return 1

    failed = []
    with conn:
        for name, fetch_jobs in SOURCES.items():
            # One broken source must not stop the others.
            try:
                jobs = fetch_jobs(search)
            except FetchError as exc:
                logger.error("%s failed: %s", name, exc)
                failed.append(name)
                continue

            new = db.save_jobs(conn, jobs)
            logger.info("%s: %d jobs for '%s', %d new", name, len(jobs), search, new)

    # Non-zero exit code so whoever runs us (Docker, n8n) can tell something broke.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
