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
- [ ] **Phase 4 — Recommendation engine**
  Turn forecasts into a simple ranked list of "best charging windows," balancing cost and green-ness.
- [ ] **Phase 5 — Geospatial charging map**
  Plot public charging stations (filterable by connector type, region) using Ladesäulenregister data.
- [ ] **Phase 6 — Streamlit app**
  Combine forecast chart, recommendation panel, and station map into one app.
- [ ] **Phase 7 — Deployment**
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

## Tech Stack

| Layer | Tool |
|---|---|
| Data wrangling | pandas, numpy |
| Forecasting | XGBoost, Prophet |
| Geospatial | folium / plotly |
| App | Streamlit |
| Deployment | Hugging Face Spaces |

## Project Structure

```
ev-smart-charging-advisor/
├── data/
│   ├── raw/                # untouched downloads from SMARD & Ladesäulenregister
│   └── processed/          # cleaned, merged datasets
├── notebooks/
│   ├── 01_eda.ipynb        # Phase 2 — daily/weekly/seasonal patterns, price/renewable correlation
│   └── figures/            # PNGs exported from the notebook
├── models/                 # Phase 3 — trained models + backtest results (gitignored, regenerate via forecast.py)
├── src/
│   ├── config.py           # paths, SMARD filter map, Ladesäulenregister URL, bbox
│   ├── data_fetch.py       # pulls SMARD + charging station data
│   ├── clean_data.py       # Phase 2 — trims/fixes raw data into data/processed/
│   ├── forecast.py         # training + inference for price/renewable forecasts
│   └── app.py              # Streamlit app
├── requirements.txt
└── README.md
```

## Getting Started

```bash
git clone https://github.com/<your-username>/ev-smart-charging-advisor.git
cd ev-smart-charging-advisor
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

(`src/data_fetch.py`, `requirements.txt`, and the rest come in the next phase.)

## License

MIT — for the code. Underlying data stays under its original source licenses (CC BY 4.0 for SMARD; see Bundesnetzagentur terms for the charging register).
