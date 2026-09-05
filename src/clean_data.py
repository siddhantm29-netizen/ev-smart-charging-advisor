"""
clean_data.py — Phase 2: clean the raw CSVs produced by data_fetch.py into
reliable, model-ready datasets under data/processed/.

Usage:
    python src/clean_data.py --smard
    python src/clean_data.py --stations
    python src/clean_data.py --smard --stations
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
from pathlib import Path

import pandas as pd

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _latest_raw(name: str) -> Path:
    """Return the most recently modified data/raw/{name}_*.csv."""
    matches = glob.glob(str(RAW_DATA_DIR / f"{name}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"No raw file found matching {name}_*.csv in {RAW_DATA_DIR}")
    return Path(max(matches, key=os.path.getmtime))


# ---------------------------------------------------------------------------
# SMARD electricity market data
# ---------------------------------------------------------------------------

def clean_smard(df: pd.DataFrame) -> pd.DataFrame:
    """Trim the merged SMARD frame to its reliably dense window and fix known quirks:

    - SMARD's "hour" chunks are misaligned across filters for pre-mid-2024
      history, producing a long stretch with most columns null per row, plus a
      real multi-month gap around Feb–Jul 2024. A trailing 7-day null-rate
      threshold identifies where the dense, reliable window begins.
    - The newest chunk extends into the future; unpublished hours come back as
      null. Trailing mostly-null rows are dropped.
    - Small isolated gaps (≤ 3 h) within the reliable window are interpolated.
    - Germany's nuclear phase-out completed Apr 2023; nuclear_mw is all-null in
      the modern window and is filled with 0 (real value, not missing data).
    """
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime").reset_index(drop=True)

    core_cols = [c for c in df.columns if c not in ("datetime", "nuclear_mw")]

    # Drop trailing rows where the generation-mix actuals aren't published yet
    # (price arrives a day before the mix, so the tail is "mostly null", not all-null).
    mostly_null   = df[core_cols].isna().mean(axis=1) > 0.5
    last_real_idx = (~mostly_null)[::-1].idxmax()
    df = df.loc[:last_real_idx].reset_index(drop=True)

    # Find the start of the reliably dense window via a 7-day trailing null rate.
    # We use a meaningful margin above the 0.2 threshold (> 0.25) rather than
    # exactly > 0.2, because the generation-mix series lags real-time by ~1-3 h:
    # the 168-row rolling window that straddles the publish-lag zone routinely
    # shows a null rate of 0.20–0.22 (a handful of null hours in an otherwise
    # clean window). Treating that as "unreliable" would incorrectly discard all
    # history up to the current day and leave only ~2 weeks of clean data.
    null_frac        = df[core_cols].isna().mean(axis=1)
    weekly_null_rate = null_frac.rolling(24 * 7, min_periods=24 * 7).mean()
    still_unreliable = weekly_null_rate > 0.25
    start = int(still_unreliable[still_unreliable].index.max() + 1) if still_unreliable.any() else 0

    if start > 0:
        logger.info("Dropping %d early rows before the reliable dense window (starts %s)",
                    start, df.loc[start, "datetime"])
    df = df.loc[start:].reset_index(drop=True)


    # Interpolate small isolated gaps; drop anything larger.
    before_na = df[core_cols].isna().sum().sum()
    df[core_cols] = df[core_cols].interpolate(method="linear", limit=3)
    after_na  = df[core_cols].isna().sum().sum()
    if before_na:
        logger.info("Interpolated %d isolated null cells (%d remain, dropped as rows)",
                    before_na - after_na, after_na)
    df = df.dropna(subset=core_cols).reset_index(drop=True)

    df["nuclear_mw"]     = df["nuclear_mw"].fillna(0.0)
    df["renewable_mw"]   = df[["wind_onshore_mw", "wind_offshore_mw", "solar_mw",
                                "hydro_mw", "biomass_mw"]].sum(axis=1)
    df["renewable_share"] = df["renewable_mw"] / df["load_mw"]
    return df


# ---------------------------------------------------------------------------
# Ladesäulenregister charging stations
# ---------------------------------------------------------------------------

def clean_stations(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicates, coerce coordinate/power columns to numeric, and
    remove rows missing coordinates (can't be placed on a map)."""
    df     = df.copy()
    before = len(df)
    df     = df.drop_duplicates()
    if len(df) != before:
        logger.info("Dropped %d exact-duplicate rows", before - len(df))

    df["Breitengrad"] = pd.to_numeric(df["Breitengrad"], errors="coerce")
    df["Längengrad"]  = pd.to_numeric(df["Längengrad"],  errors="coerce")
    before = len(df)
    df = df.dropna(subset=["Breitengrad", "Längengrad"])
    if len(df) != before:
        logger.info("Dropped %d rows missing coordinates", before - len(df))

    for col in [c for c in df.columns if c.startswith("Nennleistung_")]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--smard",    action="store_true", help="Clean the latest raw SMARD CSV")
    parser.add_argument("--stations", action="store_true", help="Clean the latest raw charging-station CSV")
    args = parser.parse_args()

    if not args.smard and not args.stations:
        parser.print_help()
        return

    if args.smard:
        src = _latest_raw("smard_market_data")
        logger.info("Cleaning %s", src)
        df  = clean_smard(pd.read_csv(src))
        out = PROCESSED_DATA_DIR / "smard_market_data_clean.csv"
        df.to_csv(out, index=False)
        logger.info("Saved %d rows × %d cols to %s", len(df), len(df.columns), out)

    if args.stations:
        src = _latest_raw("charging_stations")
        logger.info("Cleaning %s", src)
        df  = clean_stations(pd.read_csv(src, low_memory=False))
        out = PROCESSED_DATA_DIR / "charging_stations_clean.csv"
        df.to_csv(out, index=False)
        logger.info("Saved %d rows × %d cols to %s", len(df), len(df.columns), out)


if __name__ == "__main__":
    main()
