"""
data_fetch.py — pulls raw data for the EV Smart-Charging Advisor project:

1. Electricity market data (price, generation mix, demand) from SMARD,
   the Bundesnetzagentur's electricity market data platform.
2. Public EV charging station locations from the Bundesnetzagentur's
   Ladesäulenregister.

Usage:
    python src/data_fetch.py --smard
    python src/data_fetch.py --stations
    python src/data_fetch.py --smard --stations
    python src/data_fetch.py --stations --bbox 9.5,53.3,10.4,53.8   # Hamburg area only, for a quick test
    python src/data_fetch.py --stations --max-stations 500          # cap record count while testing
    python src/data_fetch.py --smard --lookback-chunks 3 --merge    # incremental refresh (see merge_with_existing)

Both APIs are free and don't require an API key.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from config import (
    GERMANY_BBOX,
    LADESTATIONEN_URL,
    RAW_DATA_DIR,
    SMARD_BASE_URL,
    SMARD_FILTERS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ev-smart-charging-advisor/0.1 (portfolio project)"})

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def _get_with_retry(url: str, params: Optional[dict] = None, timeout: int = 30) -> requests.Response:
    """GET a URL with a small retry/backoff loop — these are free public APIs
    that occasionally hiccup under load."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_error


# ---------------------------------------------------------------------------
# SMARD — electricity market data
# ---------------------------------------------------------------------------

def _smard_available_timestamps(filter_id: int, region: str, resolution: str) -> list:
    """Return the list of chunk-start timestamps SMARD has data for."""
    url = f"{SMARD_BASE_URL}/chart_data/{filter_id}/{region}/index_{resolution}.json"
    resp = _get_with_retry(url)
    return resp.json().get("timestamps", [])


def fetch_smard_series(filter_id: int, region: str, resolution: str = "hour",
                        lookback_chunks: int = 1) -> pd.DataFrame:
    """
    Fetch one SMARD time series.

    SMARD splits its history into chunks; the 'index' endpoint returns the
    start timestamp of each chunk. This fetches the most recent
    `lookback_chunks` chunks and concatenates them — set it higher for more
    history. Chunk size depends on resolution, not filter: at resolution
    "hour" each chunk is a fixed 168-hour (1 week) window, and the newest
    chunk is a rolling window straddling "now" — hours past the current
    time come back as null placeholders (not yet published), not missing
    data to be alarmed about.
    """
    timestamps = _smard_available_timestamps(filter_id, region, resolution)
    if not timestamps:
        logger.warning("No data available for filter=%s region=%s resolution=%s",
                        filter_id, region, resolution)
        return pd.DataFrame(columns=["timestamp", "value"])

    frames = []
    for ts in timestamps[-lookback_chunks:]:
        url = (f"{SMARD_BASE_URL}/chart_data/{filter_id}/{region}/"
               f"{filter_id}_{region}_{resolution}_{ts}.json")
        resp = _get_with_retry(url)
        series = resp.json().get("series", [])
        frames.append(pd.DataFrame(series, columns=["timestamp", "value"]))
        time.sleep(0.2)  # be polite to a free public API

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="timestamp")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.sort_values("datetime").reset_index(drop=True)


def fetch_smard_all(resolution: str = "hour", lookback_chunks: int = 1) -> pd.DataFrame:
    """Fetch every series listed in SMARD_FILTERS and join them into one wide
    DataFrame, one row per timestamp."""
    merged: Optional[pd.DataFrame] = None
    for name, cfg in SMARD_FILTERS.items():
        logger.info("Fetching SMARD series: %s (filter %s, region %s)",
                    name, cfg["filter"], cfg["region"])
        df = fetch_smard_series(cfg["filter"], cfg["region"], resolution=resolution,
                                 lookback_chunks=lookback_chunks)
        df = df[["datetime", "value"]].rename(columns={"value": name})
        merged = df if merged is None else merged.merge(df, on="datetime", how="outer")

    if merged is None:
        return pd.DataFrame()
    return merged.sort_values("datetime").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Ladesäulenregister — public charging stations
# ---------------------------------------------------------------------------

def fetch_charging_stations(bbox: tuple = GERMANY_BBOX, page_size: int = 1000,
                             max_records: Optional[int] = None) -> pd.DataFrame:
    """
    Pull public charging-station records from the Bundesnetzagentur's register
    (an ArcGIS FeatureServer) within a bounding box, paginating through all
    results.

    bbox: (xmin, ymin, xmax, ymax) in WGS84 lon/lat degrees. Defaults to all
    of Germany — note that's ~200k+ records, so it can take a while. Pass a
    smaller bbox (or set max_records) while testing.
    """
    xmin, ymin, xmax, ymax = bbox
    geometry = {
        "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
        "spatialReference": {"wkid": 4326},
    }

    all_rows = []
    offset = 0
    while True:
        params = {
            "f": "json",
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        resp = _get_with_retry(LADESTATIONEN_URL, params=params, timeout=60)
        data = resp.json()

        if "error" in data:
            raise RuntimeError(f"Ladesäulenregister API error: {data['error']}")

        features = data.get("features", [])
        if not features:
            break

        all_rows.extend(feat.get("attributes", {}) for feat in features)
        logger.info("Fetched %d charging stations so far (offset %d)", len(all_rows), offset)

        if max_records and len(all_rows) >= max_records:
            all_rows = all_rows[:max_records]
            break
        if len(features) < page_size:
            break  # last page

        offset += page_size
        time.sleep(0.3)  # be polite to a free public API

    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# Saving + CLI
# ---------------------------------------------------------------------------

def save_dataframe(df: pd.DataFrame, name: str, directory: Path = RAW_DATA_DIR) -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = directory / f"{name}_{date_str}.csv"
    df.to_csv(path, index=False)
    logger.info("Saved %d rows x %d cols to %s", len(df), len(df.columns), path)
    return path


def merge_with_existing(df: pd.DataFrame, name: str, directory: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """
    Merge a freshly-fetched frame (typically a small --lookback-chunks pull)
    with the existing dated raw file for `name`, so a scheduled refresh can
    fetch just the last few weeks instead of re-pulling all of history every
    time. Fresh values win on overlapping timestamps (e.g. a hitherto-null
    generation-mix figure that's since been published). The superseded old
    file is removed so data/raw/ doesn't accumulate a dated snapshot per run.
    """
    matches = glob.glob(str(directory / f"{name}_*.csv"))
    if not matches:
        return df
    existing_path = Path(max(matches, key=os.path.getmtime))
    existing = pd.read_csv(existing_path, parse_dates=["datetime"])
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    merged = (
        pd.concat([existing, df], ignore_index=True)
        .sort_values("datetime")
        .drop_duplicates(subset="datetime", keep="last")
        .reset_index(drop=True)
    )
    existing_path.unlink()
    logger.info("Merged %d fresh rows into %d existing rows from %s (%d total after dedup)",
                len(df), len(existing), existing_path.name, len(merged))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smard", action="store_true", help="Fetch SMARD electricity market data")
    parser.add_argument("--stations", action="store_true", help="Fetch public charging station data")
    parser.add_argument("--lookback-chunks", type=int, default=1,
                         help="How many SMARD data chunks to fetch, going back from most recent (default: 1)")
    parser.add_argument("--bbox", type=str, default=None,
                         help="Charging station bounding box as 'xmin,ymin,xmax,ymax' (WGS84 lon/lat). "
                              "Defaults to all of Germany.")
    parser.add_argument("--max-stations", type=int, default=None,
                         help="Cap the number of charging-station records fetched (handy for a quick test run).")
    parser.add_argument("--merge", action="store_true",
                         help="Merge the fetched SMARD data into the existing raw file instead of treating it as "
                              "the whole history — use with a small --lookback-chunks for a fast incremental refresh.")
    args = parser.parse_args()

    if not args.smard and not args.stations:
        parser.print_help()
        return

    if args.smard:
        df = fetch_smard_all(lookback_chunks=args.lookback_chunks)
        if args.merge:
            df = merge_with_existing(df, "smard_market_data")
        save_dataframe(df, "smard_market_data")

    if args.stations:
        bbox = GERMANY_BBOX
        if args.bbox:
            bbox = tuple(float(x) for x in args.bbox.split(","))
        df = fetch_charging_stations(bbox=bbox, max_records=args.max_stations)
        save_dataframe(df, "charging_stations")


if __name__ == "__main__":
    main()