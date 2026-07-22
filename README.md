---
title: EV Smart-Charging Advisor
emoji: 🔌
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: "1.60.0"
app_file: src/app.py
pinned: false
license: mit
---

# EV Smart-Charging Advisor 🔌

Predicts the cheapest and greenest times to charge an EV in Germany, using real grid data — then recommends optimal charging windows and maps nearby public charging stations.

## Overview

Germany's electricity price and renewable share swing a lot throughout the day, depending on wind, solar, and demand. This project pulls real historical grid data, forecasts near-term price and renewable share, and turns that into a plain "charge now / wait until X" recommendation — plus a map of public charging stations. It's meant to be an actual usable tool, not just a notebook of charts.

**Status:** 🚧 In progress — see roadmap below for current phase.

## Roadmap

- [x] **Phase 1 — Data collection & cleaning**
  Pull historical electricity price, demand, and generation-mix data from SMARD; pull charging station locations from the Bundesnetzagentur's register. Clean, align time zones, handle gaps.
- [x] **Phase 2 — Exploratory data analysis**
  Understand daily/weekly/seasonal price and renewable-share patterns. Identify the features that actually matter for forecasting.
- [x] **Phase 3 — Forecasting model**
  Train a model (starting with XGBoost, comparing against Prophet) to forecast next 24-48h electricity price and renewable share.
- [x] **Phase 4 — Recommendation engine**
  Turn forecasts into a simple ranked list of "best charging windows," balancing cost and green-ness.
- [x] **Phase 5 — Geospatial charging map**
  Plot public charging stations (filterable by connector type, region) using Ladesäulenregister data.
- [x] **Phase 6 — Streamlit app**
  Combine forecast chart, recommendation panel, and station map into one app.
- [x] **Phase 7 — Deployment**
  Ship it to Hugging Face Spaces (or Streamlit Community Cloud) with a scheduled data refresh.
- [ ] **Phase 8 — Polish**
  Write-up, screenshots, and a clean portfolio-ready v1.0.

## Getting the Data

Both data sources below are free, public, and don't require an account.

### 1. Electricity market data — SMARD

SMARD (Strommarktdaten) is the Bundesnetzagentur's official electricity market data platform — hourly generation by source, demand, and day-ahead prices, going back several years. The data is freely available for public use, and data from the Market data visuals section is licensed under Creative Commons Attribution 4.0 International.

Two ways to pull it:

- **Manual export (good for a first pass):** [smard.de/en/downloadcenter/download-market-data](https://www.smard.de/en/downloadcenter/download-market-data) — pick a date range (up to 2 years per file) and download as CSV or XLSX.
- **API (better for automation):** the underlying endpoint pattern is:
  ```
  https://www.smard.de/app/chart_data/{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json
  ```
  Community-documented at [smard.api.bund.dev](https://smard.api.bund.dev). There's also a maintained Python wrapper (`deutschland` package) if you'd rather not hit raw endpoints:
  ```bash
  pip install git+https://github.com/bundesAPI/deutschland.git
  ```

Attribution required if published: **"Bundesnetzagentur | SMARD.de"**.

### 2. Public charging stations — Ladesäulenregister

The Bundesnetzagentur also maintains the official register of public EV charging points in Germany (location, connector types, power output, operator).

- **Manual export:** [Ladesäulenkarte](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenkarte/start.html) — download the full list as CSV or XLSX directly (updated roughly monthly).
- **API:** documented at [ladestationen.api.bund.dev](https://ladestationen.api.bund.dev) for automated/incremental pulls.

Data is free to download and use publicly.

## Data Notes & Known Quirks

Learned by actually running `data_fetch.py` against the live APIs (as opposed to the mocked responses it was originally written against):

- **Ladesäulenregister endpoint moved behind a token.** The Bundesnetzagentur-hosted FeatureServer documented in `bundesAPI/ladestationen-api` (`services6.arcgis.com/.../Ladesaeulenregister/FeatureServer/7`) now returns HTTP 200 with a `{"code":499,"message":"Token Required"}` body for anonymous requests. `src/config.py` instead points at Esri Deutschland's public open-data mirror of the same dataset (`services2.arcgis.com/.../Ladesaeulen_in_Deutschland/FeatureServer/0`), which needs no key and is refreshed monthly. Field names changed slightly (e.g. `Nennleistung_Ladepunkt_<n>` → `Nennleistung_Stecker<n>`, up to 6 connectors instead of 4) — `data_fetch.py` doesn't hardcode field names so this required no code changes, just the URL.
- **SMARD's `hour`-resolution chunks aren't uniform across history.** Recent chunks are consistent 168-hour (1-week) windows that align across all filters; the newest chunk is a rolling window straddling "now," so its tail hours come back as `null` until published. Older chunks (pre-mid-2024) are coarser and misaligned between filters, and there's a real multi-month gap in coverage around Feb–Jul 2024. `src/clean_data.py` trims to the last fully-dense stretch rather than trying to reconcile the older, sparse history.
- **`nuclear_mw` (filter 1224) is a dead series.** Germany's nuclear phase-out completed in April 2023, and the filter stopped receiving new chunks in Jan 2024. `clean_data.py` fills it with `0` rather than leaving it null or dropping it, since zero is the real value.
- Negative day-ahead prices are real and fairly common (~6% of hours in the current dataset) — that's the market working as intended during renewable oversupply, not a data error.
- One station (Wegberg, NRW) has an implausible latitude (55.12° — that's off the North Sea coast near Denmark, not western NRW near the Dutch border where Wegberg actually is) — a typo in the source data. Left as-is (1 row out of 109,457, not worth filtering), but a reminder the source isn't perfectly clean.

## Forecasting Model (Phase 3)

`src/forecast.py` implements a **direct multi-horizon** approach: instead of
recursively forecasting one hour at a time (which compounds error), a single
model takes `horizon` (1-48) as a feature alongside calendar features
(hour/day-of-week/month, cyclically encoded) and lag/rolling features (1h,
2h, 3h, 24h, 48h, 168h lags; 24h/168h rolling mean+std) for price, load, and
renewable share — then predicts any of the next 48 hours directly from one
feature vector computed at the forecast origin.

**Benchmarks, not just a model-vs-model comparison.** Any "real" model needs
to beat a trivial baseline to be worth using, so two are included:

- **Persistence naive** — "it'll stay whatever it is right now" (repeat the
  last known value for all 48 hours). The floor any model should clear.
- **Seasonal naive (t-168h)** — "it'll be whatever it was at this exact hour
  last week." A 168h (not 24h) lag is used so every horizon up to 48h always
  references an already-known past timestamp. This is the standard,
  much-harder-to-beat benchmark for hourly electricity series, since it gets
  daily *and* day-of-week structure for free.

Backtested on a held-out final 48h window (`python src/forecast.py --target
price` / `--target renewable_share`, then `--summary` for the combined chart):

| Target | Persistence MAE | Seasonal-naive MAE | Prophet MAE | XGBoost MAE |
|---|---|---|---|---|
| price (EUR/MWh) | 75.1 | **21.9** | 38.1 | 35.5 |
| renewable share | 0.344 | 0.128 | 0.135 | **0.109** |

**The honest finding: seasonal-naive beats both "real" models on price.**
XGBoost and Prophet both beat persistence easily, and XGBoost beats Prophet —
but neither beats just copying last week's price at the same hour (skill
scores of **-62% and -74%** vs. the seasonal-naive benchmark; see
`models/backtest_skill_score_summary.png`). Looking at
`models/backtest_price_eur_mwh_timeseries.png`, the reason is visible: the
backtest window contained two sharp overnight price crashes to near-€0, and
that same crash recurred at the same hours the week before — so seasonal-naive
reproduced it almost exactly by construction, while XGBoost/Prophet (trained
to generalize across many weeks) smoothed the dip into a shallow one and
missed its depth. Renewable-share is the opposite story: XGBoost is the only
method to beat seasonal-naive (+15% skill), since it isn't a purely repeating
weekly pattern the way this particular price event was.

This is a **single 48h backtest window**, not a rolling backtest across many
windows, and it happened to land on a week where a repeating weekly pattern
dominated — that's exactly the kind of window where a naive seasonal copy
looks unreasonably good. Before trusting any of these numbers for the
recommendation engine, the natural next steps are: (1) a rolling-origin
backtest across many windows to see whether XGBoost's edge over seasonal-naive
on renewable-share holds up and whether its price deficit is consistent or
window-specific, and (2) incorporating SMARD's forecasted-generation filters
(not currently pulled) as exogenous features, since the price swings driving
this result are supply shocks that pure lag/calendar features can't see
coming — a naive lookup of last week can only help when the shock repeats.

## Recommendation Engine (Phase 4)

`src/recommend.py` turns the Phase 3 forecasts into a plain "charge now /
wait until X" recommendation:

- **Forecasts the next 48h from the latest available data.** Price uses a
  50/50 blend of the XGBoost model and the seasonal-naive (t-168h) benchmark
  — a direct consequence of the Phase 3 finding that XGBoost alone
  underperforms seasonal-naive on price (skill -62%), so the live forecast
  hedges against that known weakness rather than trusting XGBoost alone.
  Renewable share uses XGBoost alone, since it was the one model that beat
  seasonal-naive there.
- **Scores every hour** on a 0-1 `charge_score`, min-max normalizing price
  (lower is better) and renewable share (higher is better) within the 48h
  window, blended by a user-adjustable `--alpha` (0 = cheapest only, 1 =
  greenest only, default 0.5 — see `--alpha 0` vs `--alpha 1` for how the
  ranking shifts).
- **Merges consecutive good hours into windows** rather than listing
  isolated hours, and reports a plain-language recommendation plus a ranked
  list (`recommendations/next_48h_windows.json`, `next_48h_forecast.csv`,
  and `next_48h_recommendation.png`).

```
python src/recommend.py
python src/recommend.py --alpha 0.7 --top 5
```

Example output (as of the last run): the model correctly favors midday hours
each day — when solar generation peaks, renewable share is highest, and
price is lowest — and steers clear of the evening demand-peak price spike.
This tracks directly from the Phase 2 EDA finding that price and renewable
share both pivot on the midday solar dip.

**Bug found and fixed while refreshing data for this phase:** the original
`clean_data.py` dense-window detector required a perfectly unbroken run of
non-null rows working backward from the latest data — so a single missing
hour anywhere in 2+ years of otherwise-good history (e.g. a brief
generation-data publication lag behind day-ahead price) would discard
*everything* before it. Replaced with a rolling 7-day null-rate threshold to
locate the reliable window (tolerant of isolated gaps) plus interpolation
for small (≤3h) gaps within it — see the comments in `clean_smard()`.

## Geospatial Charging Map (Phase 5)

`src/map_stations.py` plots all 109k+ public charging stations with Plotly's
`Scattermap` (MapLibre-based — no Mapbox token needed, unlike the now
deprecated `Scattermapbox`):

- **Filterable by connector type via the legend** — stations are grouped
  into 4 traces (DC fast CCS, DC fast CHAdeMO, AC Type 2, Other), colored
  consistently, and each is toggled on/off by clicking its legend entry.
  Category is picked from the *best* connector present anywhere on the
  station (a station can list up to 6 connector slots, and a slot itself is
  often multiple standards) — DC fast if it has one, else AC Type 2.
- **Filterable by region via `--bundesland`** — generates a map scoped and
  zoomed to one German state rather than filtering client-side, keeping the
  interaction model simple (a real dropdown-driven client-side region filter
  is a natural Streamlit-app upgrade for Phase 6, once there's a UI to host
  the control).

```
python src/map_stations.py                     # maps/charging_stations_germany.html (109,457 stations, ~15MB)
python src/map_stations.py --bundesland Bayern  # maps/charging_stations_bayern.html
python src/map_stations.py --max-stations 3000  # quick test / smaller file
```

Chose Plotly over the originally-planned folium: `Scattermap`'s WebGL
rendering handles 100k+ points comfortably, it needs no separate
`streamlit-folium` dependency to embed in the Phase 6 app (`st.plotly_chart`
works natively), and it needs no API token.

Connector split found: **79,373 AC Type 2**, **30,051 DC fast (CCS)**, only
**27 CHAdeMO** — matches the EU's push toward CCS as the standard DC fast
connector, with CHAdeMO (Japan-originated, mainly older Nissan/Mitsubishi
EVs) now a rounding error in new German infrastructure.

## Streamlit App (Phase 6)

`src/app.py` combines Phases 3-5 into one multi-page app, in English and
German (the project's subject is the German electricity market, and the
brief targets the German/EU energy-transition job market — so German is a
first-class language, not an afterthought):

```
streamlit run src/app.py
```

- **Home** — session stats (station count, data range, latest data point) and an overview of the other pages.
- **Forecast** — the next-48h price/renewable-share charts plus the Phase 3 backtest comparison table, so the model's honest track record (including where seasonal-naive beats it) is one click away, not buried in a README.
- **Recommendation** — the `--alpha` cost/green slider, the ranked-windows chart and table, live from `recommend.py`.
- **Charging Map** — the Phase 5 map with a real client-side region dropdown (an upgrade from the CLI's `--bundesland` flag, now that there's a UI to host it) plus the existing legend-based connector-type filter.

**Architecture:** `st.navigation`/`st.Page` (Streamlit 1.36+) builds the page
list programmatically each rerun rather than the older filename-based
`pages/` folder convention, specifically so page titles can be computed from
the current language — a static-filename nav couldn't do that. Each page is
a `render(lang)` function in `src/views/`, reusing `forecast.py`,
`recommend.py`, and `map_stations.py` directly rather than reimplementing
any computation. `src/i18n.py` holds the translation dictionary plus
locale-aware number/date formatting (German comma decimals, `DD.MM.` dates).
`src/app_data.py` centralizes `st.cache_data`-wrapped loaders so every page
shares one cache entry per dataset/model instead of each re-loading and
re-caching separately.

**Bugs found by actually driving the app** (headless Chromium + Playwright,
screenshotting every page in both languages and checking the browser
console — not just code review):
- The language switcher's own label lagged one click behind the selected
  language — `st.radio`'s label was computed from `st.session_state.lang`
  *before* the click's new value was applied within that same script run.
  Fixed by binding the widget directly via `key="lang"` (which Streamlit
  syncs to session state *before* the script re-runs) and using a
  language-neutral "🌐" label instead of translated text, sidestepping the
  chicken-and-egg problem entirely.
- Weekday abbreviations (`Wed`, `Thu`) stayed in English on the German
  pages — `strftime("%a")` is locale-dependent, and relying on the system
  having `de_DE` installed is fragile (not guaranteed on a deployment host
  like Streamlit Community Cloud or HF Spaces even though it happened to
  work locally). Fixed with a manual weekday-abbreviation lookup instead.
- The home page's "Grid data range" `st.metric` truncated
  ("2024-07-20 → 202...") since `st.metric` doesn't wrap. Switched to
  month-precision formatting ("07.2024 → 07.2026"), which is all that stat
  needs anyway and fits comfortably.

## Deployment (Phase 7)

Live at: [huggingface.co/spaces/sid009991/ev-smart-charging-advisor](https://huggingface.co/spaces/sid009991/ev-smart-charging-advisor)

Two GitHub Actions handle deployment and keeping the live app current,
without either needing a manual step after the initial setup:

- **`.github/workflows/deploy-to-hf.yml`** — on every push to `main`,
  force-pushes the repo to the Hugging Face Space's own git repo, which
  triggers HF to rebuild and restart the app. The Space is configured via
  the YAML frontmatter at the top of this README (`sdk: streamlit`,
  `app_file: src/app.py` — HF Spaces reads that block directly from the
  repo's README).
- **`.github/workflows/scheduled-refresh.yml`** — runs daily (05:00 UTC):
  pulls the last 3 weeks of SMARD data (`data_fetch.py --merge`, not a full
  2-year re-fetch), re-cleans it, regenerates the live 48h recommendation,
  and commits the result if anything changed. That commit lands on `main`,
  which triggers the deploy workflow above — so a fresh recommendation
  reaches the live app automatically, with no human in the loop.

**Deliberately not automated:** retraining the XGBoost/Prophet models
(`python src/forecast.py --target ...`) stays a manual step. Silently
retraining on a schedule would mean the live app's model could drift without
anyone reviewing the new backtest numbers first — given Phase 3's finding
that the "obvious" choice (XGBoost) doesn't always beat a naive benchmark,
that review step matters more than the convenience of full automation.

**A bug this caught before it shipped:** `models/xgboost_*.json` — the
actual trained weights `recommend.py` loads at runtime — were gitignored
alongside the (correctly-ignored) larger Prophet model files. The app would
have deployed successfully and then crashed the moment anyone opened the
Forecast or Recommendation page. Caught by checking what the deployed app
actually needs on disk before wiring up the deploy workflow, not by trial and
error against the live Space.

**Setup required outside the repo** (a one-time thing, already done for this
project): create the HF Space (SDK: Streamlit), generate a HF token with
write access, and add it as the `HF_TOKEN` secret in the GitHub repo's
Settings → Secrets and variables → Actions. Neither step has a CLI/API path
that doesn't require the account owner's login, so there's no way to script
around doing them once by hand.

## Tech Stack

| Layer | Tool |
|---|---|
| Data wrangling | pandas, numpy |
| Forecasting | XGBoost, Prophet |
| Geospatial | Plotly (`Scattermap`) |
| App | Streamlit |
| Deployment | Hugging Face Spaces |

## Project Structure

```
ev-smart-charging-advisor/
├── .github/workflows/
│   ├── deploy-to-hf.yml     # Phase 7 — mirrors main to the HF Space on every push
│   └── scheduled-refresh.yml # Phase 7 — daily data refresh + recommendation regen
├── data/
│   ├── raw/                # untouched downloads from SMARD & Ladesäulenregister
│   └── processed/          # cleaned, merged datasets
├── notebooks/
│   ├── 01_eda.ipynb        # Phase 2 — daily/weekly/seasonal patterns, price/renewable correlation
│   └── figures/            # PNGs exported from the notebook
├── models/                 # Phase 3 — trained models + backtest figures/CSVs (XGBoost weights tracked; Prophet's are gitignored, regenerate via forecast.py)
├── recommendations/        # Phase 4 — latest recommendation output (small; regenerate via recommend.py)
├── src/
│   ├── config.py           # paths, SMARD filter map, Ladesäulenregister URL, bbox
│   ├── data_fetch.py       # pulls SMARD + charging station data
│   ├── clean_data.py       # Phase 2 — trims/fixes raw data into data/processed/
│   ├── forecast.py         # Phase 3 — training + inference for price/renewable forecasts
│   ├── recommend.py        # Phase 4 — forecasts + scores next 48h into ranked charging windows
│   ├── map_stations.py     # Phase 5 — interactive charging-station map
│   ├── i18n.py             # Phase 6 — EN/DE translations + locale-aware formatting
│   ├── app_data.py         # Phase 6 — shared st.cache_data loaders for the app views
│   ├── app.py              # Phase 6 — Streamlit entry point (language switch + navigation)
│   └── views/              # Phase 6 — one render(lang) function per page
│       ├── home.py
│       ├── forecast.py
│       ├── recommendation.py
│       └── charging_map.py
├── maps/                   # Phase 5 — generated HTML maps; regenerate via map_stations.py
├── requirements.txt        # deploy/CI runtime deps
├── requirements-dev.txt    # + notebook tooling and Prophet, for one-off local dev tasks
└── README.md
```

## Getting Started

```bash
git clone https://github.com/siddhantm29-netizen/ev-smart-charging-advisor.git
cd ev-smart-charging-advisor
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt                   # + requirements-dev.txt for notebook/Prophet work

streamlit run src/app.py                          # the app — data/models already in the repo, nothing to fetch first
```

To regenerate anything from scratch instead of using what's committed:

```bash
python src/data_fetch.py --smard --stations   # pull fresh raw data (Phase 1)
python src/clean_data.py --smard --stations   # clean it (Phase 2)
python src/forecast.py --target price         # train + backtest (Phase 3; needs requirements-dev.txt for Prophet)
python src/recommend.py                       # score the next 48h (Phase 4)
python src/map_stations.py                    # rebuild the station map (Phase 5)
```

## License

MIT — for the code. Underlying data stays under its original source licenses (CC BY 4.0 for SMARD; see Bundesnetzagentur terms for the charging register).
