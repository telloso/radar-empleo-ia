"""HTTP helpers that fetch JSON with timeouts and retries."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

# 429 = too many requests (wait and retry); 5xx = the server failed, not us.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_WAIT_SECONDS = 60


class FetchError(Exception):
    """Raised when a URL cannot be fetched or does not return valid JSON."""


def get_json(url: str, params: dict | None = None, **kwargs) -> dict:
    """GET a URL and return its JSON body (see request_json for options)."""
    return request_json("GET", url, params=params, **kwargs)


def post_json(url: str, body: dict, **kwargs) -> dict:
    """POST a JSON body to a URL and return its JSON body."""
    return request_json("POST", url, body=body, **kwargs)


def request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    body: dict | None = None,
    secret: str | None = None,
    timeout: float = 10,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> dict:
    """Send an HTTP request and return its JSON body.

    Retries on timeouts, connection errors, 429 and 5xx, waiting longer each
    time (exponential backoff). Fails fast on any other 4xx, because retrying
    would get the same answer.

    `secret` is a value (like an API key inside the URL) that must never
    appear in logs or error messages.
    """
    safe_url = _hide(url, secret)

    for attempt in range(1, max_retries + 1):
        wait = backoff * 2 ** (attempt - 1)

        try:
            response = requests.request(method, url, params=params, json=body, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            # requests puts the URL in its error text, so hide the secret there too.
            logger.warning(
                "Attempt %d/%d: network error: %s", attempt, max_retries, _hide(str(exc), secret)
            )
        else:
            if response.status_code in RETRYABLE_STATUS:
                wait = _retry_after(response) or wait
                logger.warning("Attempt %d/%d: HTTP %d", attempt, max_retries, response.status_code)
            elif not response.ok:
                raise FetchError(f"HTTP {response.status_code} from {safe_url}")
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise FetchError(f"Invalid JSON from {safe_url}") from exc

        if attempt < max_retries:
            logger.info("Waiting %.0f s before retrying", wait)
            time.sleep(wait)

    raise FetchError(f"Giving up on {safe_url} after {max_retries} attempts")


def _hide(text: str, secret: str | None) -> str:
    """Replace the secret with *** so it is safe to log."""
    return text.replace(secret, "***") if secret else text


def _retry_after(response: requests.Response) -> float | None:
    """Seconds the server asked us to wait, if it said so (capped)."""
    value = response.headers.get("Retry-After", "")
    if value.isdigit():
        return min(float(value), MAX_WAIT_SECONDS)
    return None
