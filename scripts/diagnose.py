"""Quick health check of every data source; results are printed as GitHub annotations."""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fame import bref, news, wikidata, wikipedia  # noqa: E402
from fame.http import get_json  # noqa: E402


def say(msg: str) -> None:
    print(f"::notice::{msg}", flush=True)


def check(name, fn):
    t = time.time()
    try:
        say(f"{name}: OK in {time.time() - t:.1f}s -> {fn()}")
    except Exception as e:  # noqa: BLE001
        say(f"{name}: FAILED in {time.time() - t:.1f}s -> {type(e).__name__}: {str(e)[:300]}")


def bref_sample():
    rows = bref.fetch_season(2026)
    return f"{len(rows)} rows; first ids {[r['bref_id'] for r in rows[:4]]}"


def wikidata_count():
    q = "SELECT (COUNT(*) AS ?n) WHERE { ?i wdt:P2685 ?v }"
    p = get_json(wikidata.ENDPOINT, params={"query": q, "format": "json"},
                 headers={"Accept": "application/sparql-results+json"}, timeout=90)
    return f"items with P2685: {p['results']['bindings'][0]['n']['value']}"


def wikidata_lebron():
    q = 'SELECT ?i ?v WHERE { ?i wdt:P2685 ?v . FILTER(?v IN ("jamesle01", "jokicni01")) }'
    p = get_json(wikidata.ENDPOINT, params={"query": q, "format": "json"},
                 headers={"Accept": "application/sparql-results+json"}, timeout=90)
    return str([(b["i"]["value"].rsplit("/", 1)[-1], b["v"]["value"]) for b in p["results"]["bindings"]])


def wikidata_sample_values():
    q = 'SELECT ?v WHERE { wd:Q36159 wdt:P2685 ?v }'   # LeBron James
    p = get_json(wikidata.ENDPOINT, params={"query": q, "format": "json"},
                 headers={"Accept": "application/sparql-results+json"}, timeout=90)
    return str([b["v"]["value"] for b in p["results"]["bindings"]])


def wikidata_module():
    return str(wikidata.fetch(["jamesle01", "jokicni01"]))[:300]


def pageviews():
    end = date.today() - timedelta(days=1)
    return f"{sum(v for _, v in wikipedia.fetch_daily('LeBron_James', end - timedelta(days=29), end))} views in 30 days"



def google_news(window):
    from fame.http import get
    import re
    import urllib.parse
    q = urllib.parse.quote(f'"LeBron James" NBA when:{window}')
    t = time.time()
    body = get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en").decode("utf-8", "replace")
    items = len(re.findall(r"<item>", body))
    return lambda: f"{items} items for when:{window} ({time.time() - t:.1f}s)"


if __name__ == "__main__":
    for w in ("1d", "7d"):
        try:
            check(f"Google News RSS {w}", google_news(w))
        except Exception as e:  # noqa: BLE001
            say(f"Google News RSS {w}: FAILED -> {type(e).__name__}: {str(e)[:300]}")
    check("Google News second player", google_news("1d"))
    check("Basketball-Reference", bref_sample)
    check("Wikidata P2685 count", wikidata_count)
    check("Wikidata LeBron/Jokic by ID", wikidata_lebron)
    check("Wikidata LeBron's P2685 value", wikidata_sample_values)
    check("Wikidata module fetch", wikidata_module)
    check("Wikipedia page views", pageviews)
