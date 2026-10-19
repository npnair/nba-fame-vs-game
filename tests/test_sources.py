"""Parsing tests for each source, using saved samples shaped like the real responses."""

import pytest

from fame import bref, news, wikidata

BREF_PAGE = """
<html><body><table id="advanced"><thead><tr><th>Rk</th></tr></thead><tbody>
{rows}
<tr class="thead"><th>Rk</th></tr>
</tbody></table></body></html>
"""
ROW = ('<tr><th data-stat="ranker">{i}</th>'
       '<td data-stat="name_display" data-append-csv="{pid}"><a href="/players/x/{pid}.html">{name}</a></td>'
       '<td data-stat="age">27</td><td data-stat="team_name_abbr">{team}</td><td data-stat="pos">PG</td>'
       '<td data-stat="games">70</td><td data-stat="mp">2259</td><td data-stat="per">30.8</td>'
       '<td data-stat="ts_pct">.665</td><td data-stat="usg_pct">33.4</td><td data-stat="ws">15.2</td>'
       '<td data-stat="bpm">11.7</td><td data-stat="vorp">7.8</td></tr>')


def page(rows):
    return BREF_PAGE.format(rows="\n".join(rows))


def test_bref_parses_players():
    rows = [ROW.format(i=i, pid=f"p{i:03d}", name=f"Player {i}", team="OKC") for i in range(3)]
    out = bref.parse_advanced(page(rows), min_rows=1)
    assert len(out) == 3
    assert out[0] == {"bref_id": "p000", "player": "Player 0", "age": 27.0, "team": "OKC", "pos": "PG",
                      "g": 70.0, "mp": 2259.0, "per": 30.8, "ts_pct": 0.665, "usg_pct": 33.4,
                      "ws": 15.2, "bpm": 11.7, "vorp": 7.8}


def test_bref_traded_player_keeps_total_row_with_latest_team():
    rows = [ROW.format(i=1, pid="hardeja01", name="James Harden", team="2TM"),
            ROW.format(i=1, pid="hardeja01", name="James Harden", team="LAC"),
            ROW.format(i=1, pid="hardeja01", name="James Harden", team="CLE")]
    out = bref.parse_advanced(page(rows), min_rows=1)
    assert len(out) == 1 and out[0]["team"] == "CLE"


def test_bref_layout_change_is_caught():
    with pytest.raises(ValueError):
        bref.parse_advanced("<html><body>No table</body></html>")
    with pytest.raises(ValueError):
        bref.parse_advanced(page([ROW.format(i=1, pid="a01", name="A", team="BOS")]))   # 1 row < 100


def test_wikidata_parse():
    payload = {"results": {"bindings": [
        {"bref": {"value": "jamesle01"}, "item": {"value": "http://www.wikidata.org/entity/Q36159"},
         "article": {"value": "https://en.wikipedia.org/wiki/LeBron_James"},
         "instagram": {"value": "kingjames"}, "credits": {"value": "4"}},
        {"bref": {"value": "jokicni01"}, "item": {"value": "http://www.wikidata.org/entity/Q3341526"},
         "article": {"value": "https://en.wikipedia.org/wiki/Nikola_Joki%C4%87"}, "credits": {"value": "0"}},
    ]}}
    rows = {r["bref_id"]: r for r in wikidata.parse(payload)}
    assert rows["jamesle01"]["wikipedia_title"] == "LeBron_James"
    assert rows["jamesle01"]["instagram_handle"] == "kingjames" and rows["jamesle01"]["media_credits"] == 4
    assert rows["jokicni01"]["wikipedia_title"] == "Nikola_Jokić" and rows["jokicni01"]["tiktok_handle"] == ""


def test_wikidata_query_only_includes_safe_ids():
    q = wikidata.build_query(["jamesle01", 'bad" } DROP', "jamesle01"])
    assert '"jamesle01"' in q and "DROP" not in q and q.count('"jamesle01"') == 1


def test_news_query_strips_accents_and_adds_context():
    assert news.default_query("Nikola Jokić") == '"Nikola Jokic" (NBA OR basketball)'
