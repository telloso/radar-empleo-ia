"""HTTP helper that fetches JSON with timeouts and retries."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

# 429 = too many requests (wait and retry); 5xx = the server failed, not us.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_WAIT_SECONDS = 60


class FetchError(Exception):
    """Raised when a URL cannot be fetched or does not return valid JSON."""


def get_json(
    url: str,
    params: dict | None = None,
    *,
    timeout: float = 10,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> dict:
    """GET a URL and return its JSON body.

    Retries on timeouts, connection errors, 429 and 5xx, waiting longer each
    time (exponential backoff). Fails fast on any other 4xx, because retrying
    would get the same answer.
    """
    for attempt in range(1, max_retries + 1):
        wait = backoff * 2 ** (attempt - 1)

        try:
            response = requests.get(url, params=params, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning("Attempt %d/%d: network error: %s", attempt, max_retries, exc)
        else:
            if response.status_code in RETRYABLE_STATUS:
                wait = _retry_after(response) or wait
                logger.warning("Attempt %d/%d: HTTP %d", attempt, max_retries, response.status_code)
            elif not response.ok:
                raise FetchError(f"HTTP {response.status_code} from {url}")
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise FetchError(f"Invalid JSON from {url}") from exc

        if attempt < max_retries:
            logger.info("Waiting %.0f s before retrying", wait)
            time.sleep(wait)

    raise FetchError(f"Giving up on {url} after {max_retries} attempts")


def _retry_after(response: requests.Response) -> float | None:
    """Seconds the server asked us to wait, if it said so (capped)."""
    value = response.headers.get("Retry-After", "")
    if value.isdigit():
        return min(float(value), MAX_WAIT_SECONDS)
    return None
