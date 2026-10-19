"""Daily pipeline: extract every source into raw/, then build the dbt models and export the results.

    python scripts/refresh.py                 # full run (about 30 minutes, mostly the news API's rate limit)
    python scripts/refresh.py --skip-news     # everything except news counts (a few minutes)
    python scripts/refresh.py --models-only   # rebuild dbt models and exports from the raw files already saved

A source that fails keeps its last saved data, and the run reports it at the end, so one flaky
API never wipes out the chart.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fame import bref, news, wikidata, wikipedia  # noqa: E402

RAW, DATA = ROOT / "raw", ROOT / "data"
PREV_SEASON, CUR_SEASON = 2026, 2027      # Basketball-Reference labels seasons by end year
PREV_MIN_MINUTES, CUR_MIN_MINUTES = 1000, 150
PAGEVIEW_DAYS_KEPT = 400

problems: list[str] = []


def note(msg: str, error: bool = False) -> None:
    print(msg, file=sys.stderr if error else sys.stdout, flush=True)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{'warning' if error else 'notice'}::{msg}", flush=True)
    if error:
        problems.append(msg)


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(RAW / f"{name}.csv", index=False)


def load(name: str) -> pd.DataFrame | None:
    path = RAW / f"{name}.csv"
    return pd.read_csv(path, dtype={"bref_id": str}) if path.exists() else None


# ---------------------------------------------------------------- extract
def extract_stats() -> pd.DataFrame:
    frames = []
    for season, refetch in ((PREV_SEASON, load(f"bref_advanced_{PREV_SEASON}") is None), (CUR_SEASON, True)):
        if refetch:
            try:
                rows = bref.fetch_season(season, min_rows=100 if season == PREV_SEASON else 1)
                if rows is None:
                    note(f"{season - 1}-{str(season)[2:]} stats aren't posted yet")
                else:
                    save(pd.DataFrame(rows), f"bref_advanced_{season}")
                    note(f"Season {season}: {len(rows)} players")
            except Exception as e:  # noqa: BLE001 - keep the last good file
                note(f"Basketball-Reference {season} failed, keeping saved data: {e}", error=True)
        df = load(f"bref_advanced_{season}")
        if df is not None:
            frames.append(df.assign(season=season))
    if not frames:
        raise SystemExit("No season stats available at all; stopping.")
    return pd.concat(frames, ignore_index=True)


def player_pool(stats: pd.DataFrame) -> list[str]:
    prev = stats[(stats.season == PREV_SEASON) & (stats.mp >= PREV_MIN_MINUTES)].bref_id
    cur = stats[(stats.season == CUR_SEASON) & (stats.mp >= CUR_MIN_MINUTES)].bref_id
    return sorted(set(prev) | set(cur))


def extract_registry(pool: list[str]) -> pd.DataFrame:
    try:
        reg = pd.DataFrame(wikidata.fetch(pool))
        save(reg, "registry")
        note(f"Wikidata: matched {len(reg)} of {len(pool)} players")
    except Exception as e:  # noqa: BLE001
        note(f"Wikidata failed, keeping saved registry: {e}", error=True)
        reg = load("registry")
        if reg is None:
            raise SystemExit("No player registry available; stopping.")
    overrides = DATA / "overrides.csv"
    if overrides.exists():
        ov = pd.read_csv(overrides, dtype=str).fillna("")
        for _, o in ov.iterrows():
            if o.get("wikipedia_title"):
                reg.loc[reg.bref_id == o.bref_id, "wikipedia_title"] = o.wikipedia_title
    return reg.fillna({"wikipedia_title": "", "instagram_handle": "", "tiktok_handle": ""})


def extract_pageviews(reg: pd.DataFrame, pool: list[str]) -> None:
    titles = {r.bref_id: r.wikipedia_title for r in reg.itertuples() if r.bref_id in pool and r.wikipedia_title}
    rows, failed = wikipedia.fetch_all(titles)
    if failed:
        note(f"Wikipedia page views failed for {len(failed)} players: {', '.join(failed[:10])}", error=True)
    new = pd.DataFrame(rows, columns=["bref_id", "date", "views"])
    old = load("pageviews_daily")
    merged = pd.concat([old, new]) if old is not None else new
    merged = merged.drop_duplicates(["bref_id", "date"], keep="last").sort_values(["bref_id", "date"])
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=PAGEVIEW_DAYS_KEPT)).strftime("%Y-%m-%d")
    save(merged[merged.date >= cutoff], "pageviews_daily")
    note(f"Wikipedia: {len(titles) - len(failed)} players, {len(new)} daily rows")


def extract_news(stats: pd.DataFrame, pool: list[str]) -> None:
    names = stats.sort_values("season").drop_duplicates("bref_id", keep="last").set_index("bref_id").player
    queries = {b: news.default_query(names[b]) for b in pool if b in names}
    overrides = DATA / "overrides.csv"
    if overrides.exists():
        for _, o in pd.read_csv(overrides, dtype=str).fillna("").iterrows():
            if o.get("news_query") and o.bref_id in queries:
                queries[o.bref_id] = o.news_query
    counts, failed = news.fetch_all(queries)
    if failed:
        note(f"News counts failed for {len(failed)} players (they keep their last count)", error=True)
    today = date.today().isoformat()
    new = pd.DataFrame([{"as_of": today, "bref_id": b, "articles_30d": n} for b, n in counts.items()])
    old = load("news_counts")
    merged = pd.concat([old, new]) if old is not None else new
    save(merged.drop_duplicates(["as_of", "bref_id"], keep="last").sort_values(["as_of", "bref_id"]), "news_counts")
    note(f"News: {len(counts)} players counted")


def sync_social_template(reg: pd.DataFrame, stats: pd.DataFrame, pool: list[str]) -> None:
    """Add a row for every new pool player to data/social_followers.csv, never touching typed numbers."""
    path = DATA / "social_followers.csv"
    cols = ["bref_id", "player", "instagram_handle", "instagram_followers", "tiktok_handle", "tiktok_followers", "as_of"]
    current = pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame(columns=cols)
    names = stats.sort_values("season").drop_duplicates("bref_id", keep="last").set_index("bref_id").player
    handles = reg.set_index("bref_id")
    added = []
    for b in pool:
        if b in set(current.bref_id):
            continue
        h = handles.loc[b] if b in handles.index else None
        added.append({"bref_id": b, "player": names.get(b, ""),
                      "instagram_handle": "" if h is None else h.instagram_handle,
                      "instagram_followers": "",
                      "tiktok_handle": "" if h is None else h.tiktok_handle,
                      "tiktok_followers": "", "as_of": ""})
    if added:
        current = pd.concat([current, pd.DataFrame(added)], ignore_index=True)
    # Fill in handles Wikidata learned about since the row was added, if the cell is still empty
    for col in ("instagram_handle", "tiktok_handle"):
        missing = current[col].eq("") & current.bref_id.isin(handles.index)
        current.loc[missing, col] = current.loc[missing, "bref_id"].map(handles[col]).fillna("")
    current[cols].sort_values("player").to_csv(path, index=False)
    if added:
        note(f"Added {len(added)} players to data/social_followers.csv")


# ---------------------------------------------------------------- transform + export
RAW_HEADERS = {
    f"bref_advanced_{PREV_SEASON}": bref.COLUMNS,
    f"bref_advanced_{CUR_SEASON}": bref.COLUMNS,
    "pool": ["bref_id"],
    "registry": ["bref_id", "wikidata_id", "wikipedia_title", "instagram_handle", "tiktok_handle", "media_credits"],
    "pageviews_daily": ["bref_id", "date", "views"],
    "news_counts": ["as_of", "bref_id", "articles_30d"],
}
SOCIAL_HEADER = "bref_id,player,instagram_handle,instagram_followers,tiktok_handle,tiktok_followers,as_of\n"


def ensure_raw_files() -> None:
    """dbt reads every source file, so write a header-only file for any source with no data yet."""
    RAW.mkdir(exist_ok=True)
    for name, cols in RAW_HEADERS.items():
        path = RAW / f"{name}.csv"
        if not path.exists():
            path.write_text(",".join(cols) + "\n")
    social = DATA / "social_followers.csv"
    if not social.exists():
        social.write_text(SOCIAL_HEADER)


def build_models() -> None:
    ensure_raw_files()
    subprocess.run(["dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt", "--quiet"],
                   check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export.py")], check=True, cwd=ROOT)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skip-news", action="store_true")
    p.add_argument("--models-only", action="store_true")
    args = p.parse_args()
    RAW.mkdir(exist_ok=True)

    if not args.models_only:
        stats = extract_stats()
        pool = player_pool(stats)
        save(pd.DataFrame({"bref_id": pool}), "pool")
        note(f"Player pool: {len(pool)} players")
        reg = extract_registry(pool)
        extract_pageviews(reg, pool)
        if not args.skip_news:
            extract_news(stats, pool)
        sync_social_template(reg, stats, pool)

    build_models()
    if problems:
        note(f"Finished with {len(problems)} source problem(s); see warnings above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
