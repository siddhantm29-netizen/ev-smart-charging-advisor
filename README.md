# EV Smart-Charging Advisor 🔌

Predicts the cheapest and greenest times to charge an EV in Germany, using real grid data — then recommends optimal charging windows and maps nearby public charging stations.

## Overview

Germany's electricity price and renewable share swing a lot throughout the day, depending on wind, solar, and demand. This project pulls real historical grid data, forecasts near-term price and renewable share, and turns that into a plain "charge now / wait until X" recommendation — plus a map of public charging stations. It's meant to be an actual usable tool, not just a notebook of charts.

**Status:** 🚧 In progress — see roadmap below for current phase.

## Roadmap

- [ ] **Phase 1 — Data collection & cleaning**
  Pull historical electricity price, demand, and generation-mix data from SMARD; pull charging station locations from the Bundesnetzagentur's register. Clean, align time zones, handle gaps.
- [ ] **Phase 2 — Exploratory data analysis**
  Understand daily/weekly/seasonal price and renewable-share patterns. Identify the features that actually matter for forecasting.
- [ ] **Phase 3 — Forecasting model**
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

SMARD (Strommarktdaten) is the Bundesnetzagentur's official electricity market data platform — hourly generation by source, demand, and day-ahead prices, going back several years. <cite index="2-1">The data is freely available for public use, and data from the Market data visuals section is licensed under Creative Commons Attribution 4.0 International.</cite>

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
│   ├── raw/            # untouched downloads from SMARD & Ladesäulenregister
│   └── processed/       # cleaned, merged datasets
├── notebooks/           # EDA and model experimentation
├── src/
│   ├── data_fetch.py     # pulls SMARD + charging station data
│   ├── forecast.py       # training + inference for price/renewable forecasts
│   └── app.py             # Streamlit app
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
