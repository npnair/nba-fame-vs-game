"""Small HTTP helper: polite user agent, retries with backoff, no third-party dependencies."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "nba-fame-vs-game/1.0 (https://github.com/npnair/nba-fame-vs-game; portfolio project)"


class FetchError(RuntimeError):
    pass


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        retries: int = 3, backoff: float = 5.0, timeout: float = 30.0) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                break                      # retrying won't help
            wait = backoff * (attempt + 1) * (3 if e.code == 429 else 1)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(backoff * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def get_json(url: str, **kwargs) -> dict:
    body = get(url, **kwargs)
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        snippet = body[:200].decode("utf-8", "replace")
        raise FetchError(f"{url}: response was not JSON ({snippet!r})") from e
