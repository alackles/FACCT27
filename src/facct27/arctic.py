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
    def __init__(self, min_interval=1.0, max_retries=8, session=None,
                 sleep=time.sleep, clock=time.monotonic, log=print):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.clock = clock
        self.log = log
        self._last = None
        self.requests_made = 0

    def _wait_turn(self):
        if self._last is not None:
            remaining = self.min_interval - (self.clock() - self._last)
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.clock()

    def _backoff(self, attempt, why):
        if attempt == self.max_retries:
            return  # out of attempts; get() raises next
        wait = min(120, 5 * 2 ** attempt)
        self.log(f"  retry {attempt + 1}/{self.max_retries} in {wait}s ({why})", flush=True)
        self.sleep(wait)

    def get(self, endpoint, params=None):
        """GET `endpoint` (e.g. "posts/search") and return the `data` field."""
        url = f"{BASE_URL}/{endpoint}"
        last = None
        for attempt in range(self.max_retries + 1):
            self._wait_turn()
            self.requests_made += 1
            try:
                resp = self.session.get(url, params=params, timeout=90)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise
                last = type(e).__name__
                self._backoff(attempt, last)
                continue

            if resp.status_code == 429:
                last = "429"
                reset = resp.headers.get("X-RateLimit-Reset", "")
                if reset.isdigit() and attempt < self.max_retries:
                    self.log(f"  rate limited; waiting {int(reset) + 1}s", flush=True)
                    self.sleep(int(reset) + 1)
                else:
                    self._backoff(attempt, last)
                continue
            if resp.status_code >= 500:
                last = str(resp.status_code)
                self._backoff(attempt, last)
                continue

            body = resp.json()
            error = body.get("error")
            if error is None:
                return body["data"]
            if "timeout" in error.lower():
                raise ApiTimeout(error)
            raise ApiError(f"{resp.status_code} {error}")

        raise ApiError(f"gave up on {endpoint} after {self.max_retries + 1} attempts "
                       f"(last: {last})")
