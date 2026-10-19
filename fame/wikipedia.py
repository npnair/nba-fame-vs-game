"""Daily English Wikipedia page views per player (Wikimedia REST API, no key needed)."""

from __future__ import annotations

import time
import urllib.parse
from datetime import date, timedelta

from .http import FetchError, get_json

URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
       "{title}/daily/{start}/{end}")


def fetch_daily(title: str, start: date, end: date) -> list[tuple[str, int]]:
    url = URL.format(title=urllib.parse.quote(title.replace(" ", "_"), safe=""),
                     start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    payload = get_json(url)
    return [(item["timestamp"][:8], int(item["views"])) for item in payload.get("items", [])]


def fetch_all(titles: dict[str, str], days: int = 45, pause: float = 0.1) -> tuple[list[dict], list[str]]:
    """titles maps bref_id -> Wikipedia title. Returns (rows, bref_ids that failed)."""
    end = date.today() - timedelta(days=1)       # yesterday is the latest complete day
    start = end - timedelta(days=days - 1)
    rows, failed = [], []
    for bref_id, title in titles.items():
        if not title:
            continue
        try:
            for day, views in fetch_daily(title, start, end):
                rows.append({"bref_id": bref_id, "date": f"{day[:4]}-{day[4:6]}-{day[6:]}", "views": views})
        except FetchError:
            failed.append(bref_id)
        time.sleep(pause)
    return rows, failed
