"""
clean_data.py — Phase 2 of the roadmap: clean the raw CSVs produced by
data_fetch.py into reliable, model-ready datasets under data/processed/.

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
    """Find the most recently modified data/raw/{name}_*.csv."""
    matches = glob.glob(str(RAW_DATA_DIR / f"{name}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"No raw file found matching {name}_*.csv in {RAW_DATA_DIR}")
    return Path(max(matches, key=os.path.getmtime))


# ---------------------------------------------------------------------------
# SMARD electricity market data
# ---------------------------------------------------------------------------

def clean_smard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trim the merged SMARD series to a reliably dense window and fix known
    data-source quirks:

    - SMARD's "hour" resolution chunking is not uniform across history: recent
      chunks are consistent 1-week windows that line up across all filters,
      but older chunks are coarser and misaligned between filters, producing
      a long stretch where only ~1 of 12 columns is populated per row, plus a
      multi-month gap around Feb-Jul 2024 (likely a chunking-scheme change on
      SMARD's side). We only keep the first fully-dense stretch found,
      working backward from the most recent data.
    - The newest hours are a rolling "current chunk" that extends into the
      future; hours not yet realized/published come back as null. These
      trailing all-null rows are dropped.
    - Germany completed its nuclear phase-out in April 2023; the nuclear_mw
      filter (1224) stopped receiving new chunks in Jan 2024, so it is null
      for the entire modern window. That's a real zero, not missing data —
      filled with 0 rather than left null or dropped.
    """
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime").reset_index(drop=True)

    core_cols = [c for c in df.columns if c not in ("datetime", "nuclear_mw")]

    # Find the last fully-dense run of rows (working from the end of history
    # backward), so we don't hardcode a cutoff date that will go stale.
    dense = df[core_cols].notna().all(axis=1)
    # trim trailing not-yet-published rows first
    last_dense_idx = dense[dense].index.max()
    df = df.loc[:last_dense_idx]
    dense = dense.loc[:last_dense_idx]

    start = last_dense_idx
    i = last_dense_idx
    while i > 0 and dense.iloc[i - 1]:
        i -= 1
    start = i

    dropped = start
    if dropped:
        logger.info("Dropping %d early rows before the reliable dense window (starts %s)",
                    dropped, df.loc[start, "datetime"])
    df = df.loc[start:].reset_index(drop=True)

    df["nuclear_mw"] = df["nuclear_mw"].fillna(0.0)

    df["renewable_mw"] = df[["wind_onshore_mw", "wind_offshore_mw", "solar_mw", "hydro_mw", "biomass_mw"]].sum(axis=1)
    df["renewable_share"] = df["renewable_mw"] / df["load_mw"]

    return df


# ---------------------------------------------------------------------------
# Ladesäulenregister charging stations
# ---------------------------------------------------------------------------

def clean_stations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Light cleaning of the raw station registry: drop exact duplicate rows,
    coerce coordinate/power columns to numeric, and drop rows missing
    coordinates (can't be placed on a map).
    """
    df = df.copy()
    before = len(df)
    df = df.drop_duplicates()
    if len(df) != before:
        logger.info("Dropped %d exact-duplicate rows", before - len(df))

    df["Breitengrad"] = pd.to_numeric(df["Breitengrad"], errors="coerce")
    df["Längengrad"] = pd.to_numeric(df["Längengrad"], errors="coerce")
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smard", action="store_true", help="Clean the latest raw SMARD CSV")
    parser.add_argument("--stations", action="store_true", help="Clean the latest raw charging-station CSV")
    args = parser.parse_args()

    if not args.smard and not args.stations:
        parser.print_help()
        return

    if args.smard:
        src = _latest_raw("smard_market_data")
        logger.info("Cleaning %s", src)
        df = clean_smard(pd.read_csv(src))
        out = PROCESSED_DATA_DIR / "smard_market_data_clean.csv"
        df.to_csv(out, index=False)
        logger.info("Saved %d rows x %d cols to %s", len(df), len(df.columns), out)

    if args.stations:
        src = _latest_raw("charging_stations")
        logger.info("Cleaning %s", src)
        df = clean_stations(pd.read_csv(src, low_memory=False))
        out = PROCESSED_DATA_DIR / "charging_stations_clean.csv"
        df.to_csv(out, index=False)
        logger.info("Saved %d rows x %d cols to %s", len(df), len(df.columns), out)


if __name__ == "__main__":
    main()
