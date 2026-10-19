"""Build the dbt project against a small synthetic dataset and check the scoring logic.

Runs offline: no API calls, so CI can check the SQL on every push.
"""

import csv
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
N = 120


def write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture(scope="module")
def mart(tmp_path_factory):
    work = tmp_path_factory.mktemp("build")
    shutil.copytree(ROOT / "dbt", work / "dbt", ignore=shutil.ignore_patterns("target", "logs"))
    ids = [f"player{i:03d}" for i in range(N)]
    stats_header = ["bref_id", "player", "age", "team", "pos", "g", "mp", "per", "ts_pct", "usg_pct", "ws", "bpm", "vorp"]
    # Player i gets better on the court as i rises; fame runs the other way for the first 10
    write(work / "raw/bref_advanced_2026.csv", stats_header,
          [[b, f"Player {i}", 25, "BOS", "G", 70, 1500 + i, 15, .55, 20, i / 10, -5 + i / 10, i / 20] for i, b in enumerate(ids)])
    write(work / "raw/bref_advanced_2027.csv", stats_header, [])
    write(work / "raw/pool.csv", ["bref_id"], [[b] for b in ids])
    write(work / "raw/registry.csv", ["bref_id", "wikidata_id", "wikipedia_title", "instagram_handle", "tiktok_handle", "media_credits"],
          [[b, f"Q{i}", f"Player_{i}", "", "", 1 if i == 0 else 0] for i, b in enumerate(ids)])
    fame = {b: (10_000_000 - i * 1000 if i < 10 else 1000 + (N - i) * 100) for i, b in enumerate(ids)}
    write(work / "raw/pageviews_daily.csv", ["bref_id", "date", "views"],
          [[b, f"2026-10-{d:02d}", fame[b] // 30] for b in ids for d in range(1, 31)])
    # Two days of news inside the window plus one stale day that must be ignored
    write(work / "raw/news_daily.csv", ["date", "bref_id", "articles"],
          [["2026-08-01", b, 999] for b in ids]
          + [["2026-10-17", b, fame[b] // 2000] for b in ids]
          + [["2026-10-18", b, fame[b] // 2000] for b in ids])
    write(work / "data/social_followers.csv",
          ["bref_id", "player", "instagram_handle", "instagram_followers", "tiktok_handle", "tiktok_followers", "as_of"],
          [["player000", "Player 0", "p0", "12.5M", "p0", "850K", "2026-10-15"],
           ["player119", "Player 119", "p119", "1,234", "", "", "2026-10-15"]])
    result = subprocess.run(["dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt"],
                            cwd=work, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-3000:]
    con = duckdb.connect(str(work / "warehouse.duckdb"), read_only=True)
    yield con
    con.close()


def row(con, bref_id):
    cols = [d[0] for d in con.execute("select * from fct_fame_vs_game limit 0").description]
    return dict(zip(cols, con.execute("select * from fct_fame_vs_game where bref_id = ?", [bref_id]).fetchone()))


def test_every_player_scored(mart):
    assert mart.execute("select count(*) from fct_fame_vs_game").fetchone()[0] == N


def test_famous_but_weak_player_is_overrated(mart):
    r = row(mart, "player000")
    assert r["fame_score"] > 90 and r["production_score"] < 10
    assert r["verdict"] == "Overrated" and r["quadrant"] == "Hype"


def test_strong_but_quiet_player_is_underrated(mart):
    r = row(mart, "player110")
    assert r["production_score"] > 85 and r["verdict"] == "Underrated" and r["quadrant"] == "Hidden gems"


def test_follower_counts_are_parsed(mart):
    assert row(mart, "player000")["instagram_followers"] == 12_500_000
    assert row(mart, "player000")["tiktok_followers"] == 850_000
    assert row(mart, "player119")["instagram_followers"] == 1234


def test_news_sums_the_last_30_days_only(mart):
    assert row(mart, "player050")["news_articles_30d"] == 2 * ((1000 + (N - 50) * 100) // 2000)


def test_missing_signals_are_skipped_not_zeroed(mart):
    r = row(mart, "player050")
    assert r["instagram_pct"] is None and r["fame_signals_used"] == 3   # page views, news, media credits
