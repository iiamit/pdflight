"""Shared HTTP client for every tool that talks to faa.gov.

One client, one set of manners. `fetch.py` and `discover_interps.py` both use
it, so backoff and User-Agent behavior cannot drift between them.

faa.gov may throttle or block datacenter egress, and the daily check workflow
raises that exposure. The mitigations are all here: sequential requests rather
than parallel, exponential backoff with jitter on 429 and 5xx, Retry-After
honored when the server sends it, a browser-like User-Agent, and conditional
requests so an unchanged document costs one 304 instead of a download.

The transport is injectable so the test suite exercises every path, including
retries and redirects, without touching the network.
"""

import random
import time

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

RETRY_STATUSES = frozenset([408, 425, 429, 500, 502, 503, 504])
DEFAULT_TIMEOUT = 60.0
DEFAULT_ATTEMPTS = 5
DEFAULT_BASE_DELAY = 1.0
MAX_DELAY = 60.0


class FetchError(Exception):
    """A request could not be completed after exhausting retries."""


class Response:
    def __init__(self, status, headers, body, url):
        self.status = status
        self.headers = {str(k).lower(): v for k, v in dict(headers or {}).items()}
        self.body = body or b""
        self.url = url

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def not_modified(self):
        return self.status == 304

    def header(self, name, default=None):
        return self.headers.get(name.lower(), default)

    @property
    def content_type(self):
        value = self.header("content-type")
        return value.split(";")[0].strip() if value else None

    @property
    def content_length(self):
        value = self.header("content-length")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def __repr__(self):
        return "<Response %d %s %d bytes>" % (self.status, self.url, len(self.body))


def _httpx_transport(timeout):
    """Default transport. Imported lazily so tests never need httpx."""
    import httpx

    client = httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )

    def transport(method, url, headers):
        reply = client.request(method, url, headers=headers)
        return (
            reply.status_code,
            dict(reply.headers),
            reply.content if method != "HEAD" else b"",
            str(reply.url),
        )

    return transport


class Client:
    """Sequential HTTP client with backoff. Never issues concurrent requests."""

    def __init__(self, transport=None, attempts=DEFAULT_ATTEMPTS,
                 base_delay=DEFAULT_BASE_DELAY, timeout=DEFAULT_TIMEOUT,
                 sleep=time.sleep, jitter=random.random):
        self._transport = transport or _httpx_transport(timeout)
        self.attempts = attempts
        self.base_delay = base_delay
        self.sleep = sleep
        self.jitter = jitter
        self.request_count = 0

    def _delay(self, attempt, response):
        if response is not None:
            retry_after = response.header("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), MAX_DELAY)
                except ValueError:
                    pass
        return min(self.base_delay * (2 ** attempt) + self.jitter(), MAX_DELAY)

    def request(self, method, url, headers=None):
        sent = dict(headers or {})
        sent.setdefault("User-Agent", USER_AGENT)

        last = None
        for attempt in range(self.attempts):
            self.request_count += 1
            try:
                status, reply_headers, body, final_url = self._transport(
                    method, url, sent)
                response = Response(status, reply_headers, body, final_url)
            except Exception as exc:  # transport-level failure, worth a retry
                last = exc
                if attempt == self.attempts - 1:
                    raise FetchError("%s %s failed: %s" % (method, url, exc))
                self.sleep(self._delay(attempt, None))
                continue

            if response.status not in RETRY_STATUSES:
                return response

            last = response
            if attempt == self.attempts - 1:
                return response
            self.sleep(self._delay(attempt, response))

        raise FetchError("%s %s exhausted %d attempts (last: %r)"
                         % (method, url, self.attempts, last))

    def head(self, url, headers=None):
        return self.request("HEAD", url, headers)

    def get(self, url, etag=None, last_modified=None, headers=None):
        sent = dict(headers or {})
        if etag:
            sent["If-None-Match"] = etag
        if last_modified:
            sent["If-Modified-Since"] = last_modified
        return self.request("GET", url, sent)


def conditional_headers(state_entry):
    """Build validator headers from a state/check.json entry."""
    if not state_entry:
        return {}
    out = {}
    if state_entry.get("etag"):
        out["If-None-Match"] = state_entry["etag"]
    if state_entry.get("last_modified"):
        out["If-Modified-Since"] = state_entry["last_modified"]
    return out
