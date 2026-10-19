# Fame vs Game

**Is an NBA player's fame earned on the court?** This project scores every regular NBA player twice, once for how well they play and once for how much attention they get, and plots one against the other. Players far above the diagonal are more famous than their play justifies. Players far below it are better than their fame suggests.

**Live chart:** https://npnair.github.io/nba-fame-vs-game/

The data refreshes every morning through an automated pipeline: Python extracts five public sources, a dbt project on DuckDB models them into scores, tests check the result, and GitHub Actions publishes the page.

## The two scores

**Game (x axis).** On-court value from Basketball-Reference's advanced stats: half VORP (total value over a replacement player, which rewards playing time) and half BPM (value per 100 possessions), each ranked within the season. Last season's numbers carry the score early on, and the 2026–27 season takes over as minutes accumulate (half weight at 1,000 minutes).

**Fame (y axis).** A weighted blend of five signals, each converted to a percentile within the player pool:

| Signal | Source | Weight | Refresh |
|---|---|---|---|
| Wikipedia page views, last 30 days | Wikimedia REST API | 30% | Daily |
| News articles mentioning the player, last 30 days | GDELT DOC 2.0 API | 25% | Daily |
| Instagram followers | Public profiles, entered by hand | 20% | Monthly |
| TikTok followers | Public profiles, entered by hand | 15% | Monthly |
| Film and TV credits | Wikidata (cast member or voice actor) | 10% | Daily |

A player missing a signal (no TikTok account, for example) is scored on the signals they have, with the weights rescaled. Both scores are re-ranked to percentiles so the axes run evenly from 0 to 100.

**Verdict.** Gap = game minus fame. A gap of +25 or more is **underrated**, −25 or less is **overrated**, anything between is **fairly rated**. The chart's quadrants split at 50: Stars (top right), Hype (top left), Hidden gems (bottom right) and Under the radar (bottom left).

On the live page you can drag sliders to reweight the fame signals and watch players move.

## Pipeline

```
Basketball-Reference ─┐
Wikidata ─────────────┤                       ┌── stg_* (clean, type, dedupe)
Wikipedia page views ─┼─► scripts/refresh.py ─► raw/*.csv ─► dbt (DuckDB) ─┼── int_production, int_fame_signals
GDELT news ───────────┤                       └── fct_fame_vs_game (+ tests)
social_followers.csv ─┘                                                 │
                                                                        ▼
                                          scripts/export.py ─► docs/data/fame.js (web page)
                                                             └► results/*.csv (latest + daily history)
```

- **Extract** (`fame/`, `scripts/refresh.py`): one module per source. Wikidata maps each Basketball-Reference player ID to their Wikipedia article and social handles in a single SPARQL query. News queries add "NBA OR basketball" so that common names don't match unrelated people.
- **Fail safe:** each source runs independently. If one fails, its last saved data stays in place, the run logs a warning, and the chart still updates from everything else.
- **Transform** (`dbt/`): staging models cast and clean the raw CSVs, intermediate models compute production and per-signal percentiles, and the `fct_fame_vs_game` mart combines them. Weights and thresholds live in `dbt_project.yml` vars.
- **Test:** dbt tests check uniqueness, nulls, allowed values, score ranges and signal coverage on every run. `pytest` checks the source parsers and builds the full dbt project against synthetic data, so the SQL is verified on every push without any network calls.
- **Publish:** GitHub Actions commits the refreshed data and deploys the page to GitHub Pages.
- **History:** `results/history.csv` gets one row per player per day, so you can see how each player's standing changes over the season.

## Updating follower counts (monthly)

`data/social_followers.csv` lists every player in the pool with their Instagram and TikTok handles (from Wikidata) and blank follower columns. Fill in the numbers from the public profiles. Any of these formats work: `12,345,678`, `12.3M`, `850K`. Set `as_of` to the date you checked, commit, and the next run picks them up. New players are added to the file automatically with their handles filled in.

## Run it yourself

```bash
git clone https://github.com/npnair/nba-fame-vs-game.git
cd nba-fame-vs-game
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/refresh.py --skip-news   # pull data and build (a few minutes)
python scripts/refresh.py               # full run including news (about 30 minutes, rate-limited API)
python scripts/refresh.py --models-only # rebuild models from saved raw data only
pytest                                  # tests
python -m http.server -d docs           # view the page at http://localhost:8000
```

Query the warehouse directly: `duckdb warehouse.duckdb "select player_name, production_score, fame_score, gap from fct_fame_vs_game order by gap desc limit 10"`.

## Project structure

```
fame/                 source extractors (bref, wikidata, wikipedia, news) and an HTTP helper
scripts/refresh.py    the daily pipeline
scripts/export.py     mart -> web data and result CSVs
dbt/                  dbt project: staging, intermediate and mart models, macros, tests
raw/                  extracted source data (committed, so every run is reproducible)
data/                 hand-maintained inputs: follower counts and name overrides
results/              latest scores and daily history
docs/                 the web page (GitHub Pages)
tests/                parser tests and an offline dbt build test
```

## Limitations

- Page views and news coverage spike with injuries, trades and controversies, not only good play. A 30-day window smooths that but doesn't remove it.
- Follower counts are entered by hand, so they're only as fresh as the last monthly update.
- Production uses box-score metrics (BPM, VORP), which underrate elite defenders who don't fill the box score.
- Players change teams in the offseason, but their team label updates only once they play for the new team.

## Data sources and terms

[Basketball-Reference](https://www.basketball-reference.com/) (one or two requests a day, within its published rate limits), [Wikimedia page views API](https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews), [GDELT](https://www.gdeltproject.org/), [Wikidata](https://www.wikidata.org/) (CC0). Instagram and TikTok counts are read manually from public profiles. Nothing is scraped from either platform.

MIT license. Not affiliated with the NBA or any team.
