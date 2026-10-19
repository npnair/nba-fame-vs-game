"""Player registry from Wikidata: Wikipedia article, Instagram and TikTok handles, film and TV credits.

Wikidata links every NBA player to their Basketball-Reference ID (property P2685), so one
SPARQL query maps the whole player pool.
"""

from __future__ import annotations

import urllib.parse

from .http import get_json

ENDPOINT = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?bref ?item (SAMPLE(?article) AS ?article) (SAMPLE(?insta) AS ?instagram)
       (SAMPLE(?tiktok) AS ?tiktok) (COUNT(DISTINCT ?work) AS ?credits) WHERE {
  VALUES ?bref { %s }
  ?item wdt:P2685 ?bref .
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
  OPTIONAL { ?item wdt:P2003 ?insta . }
  OPTIONAL { ?item wdt:P7085 ?tiktok . }
  OPTIONAL { { ?work wdt:P161 ?item . } UNION { ?work wdt:P725 ?item . } }
}
GROUP BY ?bref ?item
"""
# P161 = cast member of a film or TV production, P725 = voice actor


def build_query(bref_ids: list[str]) -> str:
    values = " ".join(f'"{b}"' for b in sorted(set(bref_ids)) if b.isalnum())
    return QUERY % values


def parse(payload: dict) -> list[dict]:
    rows = {}
    for b in payload["results"]["bindings"]:
        bref = b["bref"]["value"]
        article = b.get("article", {}).get("value", "")
        title = urllib.parse.unquote(article.rsplit("/", 1)[-1]) if article else ""
        row = {
            "bref_id": bref,
            "wikidata_id": b["item"]["value"].rsplit("/", 1)[-1],
            "wikipedia_title": title,
            "instagram_handle": b.get("instagram", {}).get("value", ""),
            "tiktok_handle": b.get("tiktok", {}).get("value", ""),
            "media_credits": int(b.get("credits", {}).get("value", 0)),
        }
        rows.setdefault(bref, row)   # a player rarely has two Wikidata items; keep the first
    return list(rows.values())


def fetch(bref_ids: list[str], chunk: int = 150) -> list[dict]:
    out: list[dict] = []
    ids = sorted(set(bref_ids))
    for i in range(0, len(ids), chunk):
        payload = get_json(ENDPOINT, params={"query": build_query(ids[i:i + chunk]), "format": "json"},
                           headers={"Accept": "application/sparql-results+json"}, timeout=90)
        out.extend(parse(payload))
    return out
