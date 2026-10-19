"""News coverage: articles mentioning each player in the last day, from Google News' public RSS search.

Each feed returns at most 100 items, so a 30-day search would cap out for every star. Counting one
day at a time stays under the cap for nearly everyone; the dbt model sums the daily counts over the
last 30 days. (GDELT was the first choice, but it rejects requests from GitHub's shared servers.)
"""

from __future__ import annotations

import re
import time
import unicodedata

from .http import FetchError, get

URL = "https://news.google.com/rss/search"
FEED_CAP = 100


def ascii_name(name: str) -> str:
    """News outlets mostly print 'Nikola Jokic', not 'Nikola Jokić'."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def default_query(name: str) -> str:
    # The basketball terms keep "Jalen Williams" from matching every Jalen Williams in the news
    return f'"{ascii_name(name)}" (NBA OR basketball)'


def count_items(feed: str) -> int:
    """Distinct articles in an RSS feed (Google sometimes repeats a story under two items)."""
    links = re.findall(r"<item>.*?<link>(.*?)</link>", feed, flags=re.S)
    return len(set(links))


def daily_count(query: str) -> int:
    body = get(URL, params={"q": f"{query} when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return count_items(body.decode("utf-8", "replace"))


def fetch_all(queries: dict[str, str], pause: float = 1.0) -> tuple[dict[str, int], list[str]]:
    """queries maps bref_id -> search query. Returns ({bref_id: articles in the last day}, failed ids)."""
    counts, failed = {}, []
    consecutive_failures = 0
    for bref_id, query in queries.items():
        try:
            counts[bref_id] = daily_count(query)
            consecutive_failures = 0
        except FetchError:
            failed.append(bref_id)
            consecutive_failures += 1
            if consecutive_failures >= 5:          # the source is down or blocking us; stop early
                failed.extend(b for b in queries if b not in counts and b not in failed)
                break
        time.sleep(pause)
    return counts, failed
