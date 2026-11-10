"""Job collector: fetches offers from the configured sources and saves them in PostgreSQL."""

import logging
import os
import sys

import psycopg

import db
from http_utils import FetchError
from sources import jooble, remotive

logger = logging.getLogger("collector")

# Each source runs its own list of searches, read from an environment variable.
# Remotive asks for at most ~4 requests a day, so keep its list short.
SOURCES = {
    "remotive": (remotive.fetch_jobs, "REMOTIVE_SEARCHES"),
    "jooble": (jooble.fetch_jobs, "JOOBLE_SEARCHES"),
}
DEFAULT_SEARCHES = "python"


def parse_searches(value: str | None) -> list[str]:
    """Turn 'python, devops,,python ' into ['python', 'devops'] (no blanks, no repeats)."""
    searches = []
    for search in (value or DEFAULT_SEARCHES).split(","):
        search = search.strip()
        if search and search not in searches:
            searches.append(search)
    return searches


def collect(conn, name: str, fetch_jobs, searches: list[str]) -> bool:
    """Run every search of one source and save the jobs. Return False if it failed."""
    total = new = 0
    for search in searches:
        try:
            jobs = fetch_jobs(search)
        except FetchError as exc:
            # A quota or auth error would hit the next searches too: stop this source.
            logger.error("%s failed on '%s': %s", name, search, exc)
            return False

        # A job found by two searches is saved once; it only counts as new the first time.
        saved = db.save_jobs(conn, jobs)
        logger.info("%s: %d jobs for '%s', %d new", name, len(jobs), search, saved)
        total += len(jobs)
        new += saved

    logger.info("%s: %d jobs in %d searches, %d new", name, total, len(searches), new)
    return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        conn = db.connect()
    except psycopg.OperationalError as exc:
        # Without the database there is nowhere to save, so don't spend API requests.
        logger.error("cannot connect to the database: %s", exc)
        return 1

    failed = []
    with conn:
        for name, (fetch_jobs, env_var) in SOURCES.items():
            # One broken source must not stop the others.
            searches = parse_searches(os.getenv(env_var))
            if not collect(conn, name, fetch_jobs, searches):
                failed.append(name)

    # Non-zero exit code so whoever runs us (Docker, n8n) can tell something broke.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
