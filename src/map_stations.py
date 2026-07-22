"""
map_stations.py — Phase 5 of the roadmap: interactive map of public EV
charging stations, filterable by connector type (click a legend entry to
toggle it) and region (--bundesland generates a map scoped to one state).

Usage:
    python src/map_stations.py
    python src/map_stations.py --bundesland Bayern
    python src/map_stations.py --max-stations 5000   # quick test / smaller file
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
import plotly.graph_objects as go

from config import PROCESSED_DATA_DIR, PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAPS_DIR = PROJECT_ROOT / "maps"
MAPS_DIR.mkdir(parents=True, exist_ok=True)

# Ordered so DC fast charging (the connector type most relevant to a "can I
# charge quickly here" question) draws on top of the far more numerous AC
# points, rather than getting buried underneath them.
CONNECTOR_CATEGORIES = ["Other", "AC Type 2", "DC fast (CHAdeMO)", "DC fast (CCS)"]
CONNECTOR_COLORS = {
    "DC fast (CCS)": "#2a78d6",
    "DC fast (CHAdeMO)": "#eb6834",
    "AC Type 2": "#1baf7a",
    "Other": "#eda100",
}

STECKER_COLS = [f"Steckertypen{i}" for i in range(1, 7)]


def load_stations() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DATA_DIR / "charging_stations_clean.csv", low_memory=False)


def classify_connector(df: pd.DataFrame) -> pd.Series:
    """A station can list up to 6 connectors, and a slot itself is often a
    semicolon-joined list (a single physical socket serving multiple
    standards). Categorize by the best (fastest) connector family present
    anywhere on the station, since that's what actually determines whether
    it can rapid-charge an EV."""
    combined = df[STECKER_COLS].fillna("").agg(" ".join, axis=1)
    category = pd.Series("Other", index=df.index)
    category[combined.str.contains("Typ 2", na=False)] = "AC Type 2"
    category[combined.str.contains("CHAdeMO", na=False)] = "DC fast (CHAdeMO)"
    category[combined.str.contains("Combo 2 (CCS)", regex=False, na=False)] = "DC fast (CCS)"
    return category


def build_map(df: pd.DataFrame, region: str | None = None, category_labels: dict | None = None) -> go.Figure:
    """category_labels optionally maps each CONNECTOR_CATEGORIES entry to a
    display label (e.g. a translation) — legend/trace names use it if given,
    the category key itself otherwise."""
    labels = category_labels or {c: c for c in CONNECTOR_CATEGORIES}
    if region:
        df = df[df["Bundesland"] == region]
        if df.empty:
            raise ValueError(f"No stations found for Bundesland={region!r}")

    df = df.copy()
    df["connector_category"] = classify_connector(df)

    fig = go.Figure()
    for category in CONNECTOR_CATEGORIES:
        sub = df[df["connector_category"] == category]
        if sub.empty:
            continue
        power = sub["Nennleistung_Ladeeinrichtung__kW_"].fillna(0).round().astype(int)
        hover = (
            sub["Betreiber"].fillna("Unknown operator") + "<br>"
            + sub["Ort"].fillna("").astype(str) + ", " + sub["Bundesland"].fillna("").astype(str) + "<br>"
            + sub["Art_der_Ladeeinrichtung"].fillna("").astype(str) + " — " + power.astype(str) + " kW"
        )
        fig.add_trace(go.Scattermap(
            lat=sub["Breitengrad"], lon=sub["Längengrad"],
            mode="markers",
            marker=dict(size=5, color=CONNECTOR_COLORS[category], opacity=0.65),
            name=f"{labels[category]} ({len(sub):,})",
            text=hover,
            hoverinfo="text",
        ))

    center_lat, center_lon = df["Breitengrad"].mean(), df["Längengrad"].mean()
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon),
                  zoom=7.5 if region else 5.2),
        margin=dict(l=0, r=0, t=40, b=0),
        title=f"Public EV charging stations — {region or 'Germany'} ({len(df):,})",
        legend=dict(title=dict(text=labels.get("_legend_title", "Connector type (click to filter)"))),
        height=750,
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundesland", default=None,
                         help="Filter to one German state (e.g. Bayern, Berlin, Hamburg)")
    parser.add_argument("--max-stations", type=int, default=None,
                         help="Randomly sample down to this many stations (quick test / smaller file)")
    args = parser.parse_args()

    df = load_stations()
    if args.max_stations and len(df) > args.max_stations:
        df = df.sample(args.max_stations, random_state=0)
        logger.info("Sampled down to %d stations for a quick test", len(df))

    fig = build_map(df, region=args.bundesland)
    name = f"charging_stations_{(args.bundesland or 'germany').lower().replace(' ', '_')}.html"
    out = MAPS_DIR / name
    fig.write_html(str(out), include_plotlyjs="cdn")
    logger.info("Saved %s (%.2f MB)", out, out.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
