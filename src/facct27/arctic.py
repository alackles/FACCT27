"""Minimal client for the Arctic Shift Reddit archive API.

Arctic Shift is unauthenticated, so there are no keys to manage. The client
spaces requests out, waits out 429s using the server's reset header, and
retries transient network and 5xx failures. Query timeouts (reported as a
200 with an error body) are raised as ApiTimeout so the caller can shrink
the query rather than repeat it unchanged.
"""

import time

import requests

BASE_URL = "https://arctic-shift.photon-reddit.com/api"
USER_AGENT = "FACCT27-research-collector/0.1 (+https://github.com/alackles/FACCT27)"


class ApiError(Exception):
    """The API returned an error body we don't know how to recover from."""


class ApiTimeout(ApiError):
    """The API gave up on the query; a smaller or narrower query may succeed."""


class Client:
    def __init__(self, min_interval=1.0, max_retries=5, session=None,
                 sleep=time.sleep, clock=time.monotonic):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.clock = clock
        self._last = None
        self.requests_made = 0

    def _wait_turn(self):
        if self._last is not None:
            remaining = self.min_interval - (self.clock() - self._last)
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.clock()

    def get(self, endpoint, params=None):
        """GET `endpoint` (e.g. "posts/search") and return the `data` field."""
        url = f"{BASE_URL}/{endpoint}"
        for attempt in range(self.max_retries + 1):
            self._wait_turn()
            self.requests_made += 1
            try:
                resp = self.session.get(url, params=params, timeout=90)
            except requests.RequestException:
                if attempt == self.max_retries:
                    raise
                self.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                reset = resp.headers.get("X-RateLimit-Reset", "")
                self.sleep(float(reset) + 1 if reset.isdigit() else 2 ** attempt * 5)
                continue
            if resp.status_code >= 500:
                self.sleep(2 ** attempt)
                continue

            body = resp.json()
            error = body.get("error")
            if error is None:
                return body["data"]
            if "timeout" in error.lower():
                raise ApiTimeout(error)
            raise ApiError(f"{resp.status_code} {error}")

        raise ApiError(f"gave up on {endpoint} after {self.max_retries + 1} attempts")
