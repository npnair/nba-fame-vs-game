"""Season advanced stats (BPM, VORP, minutes) from Basketball-Reference's league page.

Two requests a day at most, well within Basketball-Reference's published rate limits.
"""

from __future__ import annotations

import re

from lxml import html

from .http import FetchError, get

URL = "https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html"
COLUMNS = ["bref_id", "player", "age", "team", "pos", "g", "mp", "per", "ts_pct", "usg_pct", "ws", "bpm", "vorp"]
MULTI_TEAM = re.compile(r"^\d+TM$|^TOT$")
STAT_ALIASES = {  # Basketball-Reference has renamed some data-stat keys over the years
    "player": ("name_display", "player"),
    "team": ("team_name_abbr", "team_id"),
    "age": ("age",), "pos": ("pos",), "g": ("games", "g"), "mp": ("mp",), "per": ("per",),
    "ts_pct": ("ts_pct",), "usg_pct": ("usg_pct",), "ws": ("ws",), "bpm": ("bpm",), "vorp": ("vorp",),
}
NUMERIC = {"age", "g", "mp", "per", "ts_pct", "usg_pct", "ws", "bpm", "vorp"}


def _cell(row, key: str):
    for alias in STAT_ALIASES[key]:
        found = row.xpath(f"./*[@data-stat='{alias}']")
        if found:
            return found[0]
    return None


def _player_id(cell) -> str | None:
    if cell is None:
        return None
    if cell.get("data-append-csv"):
        return cell.get("data-append-csv")
    href = next(iter(cell.xpath(".//a/@href")), "")
    m = re.search(r"/players/\w/([a-z0-9]+)\.html", href)
    return m.group(1) if m else None


def parse_advanced(page: str | bytes, min_rows: int = 100) -> list[dict]:
    """One row per player. Traded players keep their combined row, tagged with their latest team."""
    tree = html.fromstring(page)
    tables = tree.xpath("//table[@id='advanced' or @id='advanced_stats']")
    if not tables:
        raise ValueError("Advanced stats table not found on the page")
    players: dict[str, dict] = {}
    for row in tables[0].xpath(".//tbody/tr[not(contains(@class,'thead'))]"):
        name_cell = _cell(row, "player")
        pid = _player_id(name_cell)
        if not pid:
            continue
        rec = {"bref_id": pid, "player": name_cell.text_content().strip().rstrip("*")}
        for key in COLUMNS[2:]:
            cell = _cell(row, key)
            text = cell.text_content().strip() if cell is not None else ""
            if key in NUMERIC:
                try:
                    rec[key] = float(text) if text else None
                except ValueError:
                    rec[key] = None
            else:
                rec[key] = text
        team = rec["team"]
        if pid not in players:
            players[pid] = rec
            players[pid]["latest_team"] = None if MULTI_TEAM.match(team or "") else team
        elif not MULTI_TEAM.match(team or ""):
            players[pid]["latest_team"] = team          # rows after the combined one are per team, in order
    out = []
    for rec in players.values():
        rec["team"] = rec.pop("latest_team") or rec["team"]
        out.append(rec)
    if len(out) < min_rows:
        raise ValueError(f"Only {len(out)} players parsed; the page layout may have changed")
    return out


TEAMS = ["ATL", "BOS", "BRK", "CHI", "CHO", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
         "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHO", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
ROSTER_URL = "https://www.basketball-reference.com/teams/{team}/{season}.html"
PLAYER_LINK = re.compile(r"^/players/\w/([a-z0-9]+)\.html$")


def parse_roster(page: str | bytes) -> list[dict]:
    """Players on a team page's current roster table."""
    tree = html.fromstring(page)
    tables = tree.xpath("//table[@id='roster']")
    if not tables:
        raise ValueError("Roster table not found on the page")
    players = {}
    for link in tables[0].xpath(".//tbody//a[starts-with(@href, '/players/')]"):
        m = PLAYER_LINK.match(link.get("href", ""))
        if m:
            players.setdefault(m.group(1), link.text_content().strip())
    if not players:
        raise ValueError("Roster table has no players")
    return [{"bref_id": pid, "player": name} for pid, name in players.items()]


def fetch_rosters(season: int, pause: float = 3.5) -> tuple[list[dict], list[str]]:
    """Every team's roster. Basketball-Reference allows up to 20 requests a minute, hence the pause.
    Returns (rows, teams that failed)."""
    import time
    rows, failed = [], []
    for team in TEAMS:
        try:
            for p in parse_roster(get(ROSTER_URL.format(team=team, season=season))):
                rows.append({**p, "team": team})
        except (FetchError, ValueError):
            failed.append(team)
        time.sleep(pause)
    return rows, failed


def fetch_season(season: int, min_rows: int = 100) -> list[dict] | None:
    """Return the season's rows, or None if the season hasn't started (no page or no table yet)."""
    try:
        page = get(URL.format(season=season))
    except FetchError as e:
        if "404" in str(e):
            return None
        raise
    if b'id="advanced' not in page:
        return None
    return parse_advanced(page, min_rows=min_rows)
