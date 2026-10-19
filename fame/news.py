"""News coverage: how many articles mentioned each player in the last 30 days (GDELT DOC 2.0 API).

GDELT is free and needs no key, but asks for no more than one request every five seconds,
so a full run over ~250 players takes about 25 minutes.
"""

from __future__ import annotations

import time
import unicodedata

from .http import FetchError, get_json

URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def ascii_name(name: str) -> str:
    """News outlets mostly print 'Nikola Jokic', not 'Nikola Jokić'."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def default_query(name: str) -> str:
    # The basketball terms keep "Jalen Williams" from matching every Jalen Williams in the news
    return f'"{ascii_name(name)}" (NBA OR basketball)'


def article_count(query: str, timespan: str = "30d") -> int:
    payload = get_json(URL, params={"query": query, "mode": "timelinevolraw", "timespan": timespan,
                                    "format": "json"}, backoff=10)
    timeline = payload.get("timeline") or []
    if not timeline:
        return 0
    return int(sum(point.get("value", 0) for point in timeline[0].get("data", [])))


def fetch_all(queries: dict[str, str], pause: float = 5.5) -> tuple[dict[str, int], list[str]]:
    """queries maps bref_id -> GDELT query. Returns ({bref_id: articles}, failed bref_ids)."""
    counts, failed = {}, []
    for bref_id, query in queries.items():
        try:
            counts[bref_id] = article_count(query)
        except FetchError:
            failed.append(bref_id)
        time.sleep(pause)
    return counts, failed
