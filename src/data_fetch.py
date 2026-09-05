"""
data_fetch.py — Phase 1: pull raw data for the EV Smart-Charging Advisor.

1. Electricity market data (price, generation mix, demand) from SMARD.
2. Public EV charging station locations from the Bundesnetzagentur's
   Ladesäulenregister.

Usage:
    python src/data_fetch.py --smard
    python src/data_fetch.py --stations
    python src/data_fetch.py --smard --stations
    python src/data_fetch.py --stations --bbox 9.5,53.3,10.4,53.8   # Hamburg area
    python src/data_fetch.py --stations --max-stations 500
    python src/data_fetch.py --smard --lookback-chunks 3 --merge     # incremental refresh
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

MAX_RETRIES         = 3
RETRY_BACKOFF_SECONDS = 2


def _get_with_retry(url: str, params: dict | None = None, timeout: int = 30) -> requests.Response:
    """GET with a small exponential-backoff retry loop."""
    if MAX_RETRIES < 1:
        raise ValueError("MAX_RETRIES must be >= 1")
    last_error: Exception = RuntimeError("unreachable")
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
# SMARD electricity market data
# ---------------------------------------------------------------------------

def _smard_available_timestamps(filter_id: int, region: str, resolution: str) -> list:
    url = f"{SMARD_BASE_URL}/chart_data/{filter_id}/{region}/index_{resolution}.json"
    return _get_with_retry(url).json().get("timestamps", [])


def fetch_smard_series(
    filter_id: int,
    region: str,
    resolution: str = "hour",
    lookback_chunks: int = 1,
) -> pd.DataFrame:
    """Fetch one SMARD time series.

    SMARD splits history into fixed-size chunks; the index endpoint returns each
    chunk's start timestamp. This fetches the most recent `lookback_chunks`
    chunks and concatenates them. At resolution "hour" each chunk is 168 h; the
    newest chunk straddles "now" — hours beyond the current time return null
    (not yet published) rather than missing data."""
    timestamps = _smard_available_timestamps(filter_id, region, resolution)
    if not timestamps:
        logger.warning("No data for filter=%s region=%s resolution=%s",
                       filter_id, region, resolution)
        return pd.DataFrame(columns=["timestamp", "value"])

    frames = []
    for ts in timestamps[-lookback_chunks:]:
        url  = (f"{SMARD_BASE_URL}/chart_data/{filter_id}/{region}/"
                f"{filter_id}_{region}_{resolution}_{ts}.json")
        series = _get_with_retry(url).json().get("series", [])
        frames.append(pd.DataFrame(series, columns=["timestamp", "value"]))
        time.sleep(0.2)

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="timestamp")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.sort_values("datetime").reset_index(drop=True)


def fetch_smard_all(resolution: str = "hour", lookback_chunks: int = 1) -> pd.DataFrame:
    """Fetch every series in SMARD_FILTERS and join them into one wide DataFrame."""
    merged: pd.DataFrame | None = None
    for name, cfg in SMARD_FILTERS.items():
        logger.info("Fetching SMARD series: %s (filter %s, region %s)",
                    name, cfg["filter"], cfg["region"])
        df = fetch_smard_series(cfg["filter"], cfg["region"],
                                resolution=resolution, lookback_chunks=lookback_chunks)
        df = df[["datetime", "value"]].rename(columns={"value": name})
        merged = df if merged is None else merged.merge(df, on="datetime", how="outer")

    return pd.DataFrame() if merged is None else merged.sort_values("datetime").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Ladesäulenregister charging stations
# ---------------------------------------------------------------------------

def fetch_charging_stations(
    bbox: tuple = GERMANY_BBOX,
    page_size: int = 1000,
    max_records: int | None = None,
) -> pd.DataFrame:
    """Pull public charging-station records from the ArcGIS FeatureServer,
    paginating through all results within the bounding box.

    bbox: (xmin, ymin, xmax, ymax) in WGS84 lon/lat degrees.
    All of Germany (~200 k+ records) can take several minutes; pass a smaller
    bbox or set max_records while testing."""
    xmin, ymin, xmax, ymax = bbox
    geometry = {
        "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
        "spatialReference": {"wkid": 4326},
    }

    all_rows, offset = [], 0
    while True:
        params = {
            "f":                  "json",
            "geometry":           json.dumps(geometry),
            "geometryType":       "esriGeometryEnvelope",
            "inSR":               4326,
            "outSR":              4326,
            "spatialRel":         "esriSpatialRelIntersects",
            "outFields":          "*",
            "returnGeometry":     "false",
            "resultOffset":       offset,
            "resultRecordCount":  page_size,
        }
        data = _get_with_retry(LADESTATIONEN_URL, params=params, timeout=60).json()

        if "error" in data:
            raise RuntimeError(f"Ladesäulenregister API error: {data['error']}")

        features = data.get("features", [])
        if not features:
            break

        all_rows.extend(feat.get("attributes", {}) for feat in features)
        logger.info("Fetched %d stations so far (offset %d)", len(all_rows), offset)

        if max_records and len(all_rows) >= max_records:
            all_rows = all_rows[:max_records]
            break
        if len(features) < page_size:
            break

        offset += page_size
        time.sleep(0.3)

    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# Saving and incremental merge
# ---------------------------------------------------------------------------

def save_dataframe(df: pd.DataFrame, name: str, directory: Path = RAW_DATA_DIR) -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = directory / f"{name}_{date_str}.csv"
    df.to_csv(path, index=False)
    logger.info("Saved %d rows × %d cols to %s", len(df), len(df.columns), path)
    return path


def merge_with_existing(df: pd.DataFrame, name: str, directory: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Merge a freshly-fetched frame into the existing dated raw file, so a
    scheduled refresh only needs a small --lookback-chunks pull instead of
    re-fetching all of history. Fresh values win on overlapping timestamps.
    The superseded old file is removed so data/raw/ stays tidy."""
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--smard",    action="store_true", help="Fetch SMARD electricity market data")
    parser.add_argument("--stations", action="store_true", help="Fetch public charging station data")
    parser.add_argument("--lookback-chunks", type=int, default=1,
                        help="SMARD chunks to fetch going back from the most recent (default: 1)")
    parser.add_argument("--bbox", type=str, default=None,
                        help="Station bounding box as 'xmin,ymin,xmax,ymax' (WGS84). "
                             "Defaults to all of Germany.")
    parser.add_argument("--max-stations", type=int, default=None,
                        help="Cap charging-station records (handy for quick test runs).")
    parser.add_argument("--merge", action="store_true",
                        help="Merge fetched SMARD data into the existing raw file "
                             "(use with a small --lookback-chunks for a fast incremental refresh).")
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
        bbox = tuple(float(x) for x in args.bbox.split(",")) if args.bbox else GERMANY_BBOX
        df   = fetch_charging_stations(bbox=bbox, max_records=args.max_stations)
        save_dataframe(df, "charging_stations")


if __name__ == "__main__":
    main()