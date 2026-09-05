"""
recommend.py — Phase 4: turn Phase 3 forecasts into a ranked list of
"best charging windows" over the next 48h, balancing cost and green-ness.

Usage:
    python src/recommend.py
    python src/recommend.py --alpha 0.7   # 0 = cost only, 1 = green only
    python src/recommend.py --top 5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from config import PROJECT_ROOT
from forecast import (
    HORIZONS,
    MODELS_DIR,
    PALETTE,
    baseline_seasonal_naive,
    build_feature_frame,
    feature_columns,
    load_clean_smard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RECS_DIR = PROJECT_ROOT / "recommendations"
RECS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Forecast the next 48h from the latest available data
# ---------------------------------------------------------------------------

def load_xgb_model(target_col: str) -> XGBRegressor:
    model = XGBRegressor()
    model.load_model(str(MODELS_DIR / f"xgboost_{target_col}.json"))
    return model


def _forecast_xgb(model: XGBRegressor, origin_row: pd.Series, feature_cols: list) -> pd.Series:
    rows = pd.DataFrame([origin_row[feature_cols]] * len(HORIZONS))
    rows["horizon"] = HORIZONS
    preds = model.predict(rows[feature_cols + ["horizon"]])
    return pd.Series(preds, index=HORIZONS)


def build_forecast() -> tuple[pd.DataFrame, pd.Timestamp]:
    """Forecast price and renewable share for the next 48h from the latest
    data point (the "now" of this data snapshot).

    Price is a 50/50 XGBoost + seasonal-naive blend: backtesting found
    XGBoost alone underperforms seasonal-naive on price (-62% skill) because
    it smooths over sharp recurring weekly swings that the naive benchmark
    reproduces for free. Renewable share uses XGBoost alone (+15% skill)."""
    df      = load_clean_smard()
    feat_df = build_feature_frame(df)
    fcols   = feature_columns(feat_df)
    origin  = feat_df.index[-1]
    logger.info("Forecasting the next %dh from origin %s", len(HORIZONS), origin)

    origin_row = feat_df.loc[origin]

    xgb_price      = _forecast_xgb(load_xgb_model("price_eur_mwh"), origin_row, fcols)
    seasonal_price = baseline_seasonal_naive(df, origin, "price_eur_mwh")
    blended_price  = (xgb_price + seasonal_price) / 2

    xgb_renewable = _forecast_xgb(load_xgb_model("renewable_share"), origin_row, fcols)

    forecast_df = pd.DataFrame({
        "horizon":                  HORIZONS,
        "timestamp":                [origin + pd.Timedelta(hours=h) for h in HORIZONS],
        "price_xgboost":            xgb_price.values,
        "price_seasonal_naive":     seasonal_price.values,
        "price_forecast":           blended_price.values,
        "renewable_share_forecast": xgb_renewable.values,
    })
    return forecast_df, origin


# ---------------------------------------------------------------------------
# Score and rank charging windows
# ---------------------------------------------------------------------------

def score_windows(forecast_df: pd.DataFrame, alpha: float = 0.5) -> pd.DataFrame:
    """charge_score ∈ [0, 1], higher = better time to charge.
    alpha=0 → cheapest only, alpha=1 → greenest only.
    Both dimensions are min-max normalised within this 48h window."""
    df        = forecast_df.copy()
    price     = df["price_forecast"]
    renewable = df["renewable_share_forecast"]

    price_range     = price.max() - price.min()
    renewable_range = renewable.max() - renewable.min()

    df["price_score"] = (
        (price.max() - price) / price_range
        if price_range > 0
        else pd.Series(0.5, index=df.index)
    )
    df["renewable_score"] = (
        (renewable - renewable.min()) / renewable_range
        if renewable_range > 0
        else pd.Series(0.5, index=df.index)
    )
    df["charge_score"] = (1 - alpha) * df["price_score"] + alpha * df["renewable_score"]
    return df


def find_windows(scored_df: pd.DataFrame, top_frac: float = 0.25) -> list[dict]:
    """Merge consecutive above-threshold hours into contiguous windows."""
    df = scored_df.sort_values("horizon").reset_index(drop=True)
    threshold   = df["charge_score"].quantile(1 - top_frac)
    df["is_good"] = df["charge_score"] >= threshold
    df["group"]   = (df["is_good"] != df["is_good"].shift()).cumsum()

    windows = [
        {
            "start":               grp["timestamp"].iloc[0],
            "end":                 grp["timestamp"].iloc[-1] + pd.Timedelta(hours=1),
            "duration_h":          len(grp),
            "avg_price":           float(grp["price_forecast"].mean()),
            "avg_renewable_share": float(grp["renewable_share_forecast"].mean()),
            "avg_score":           float(grp["charge_score"].mean()),
        }
        for _, grp in df[df["is_good"]].groupby("group")
    ]
    windows.sort(key=lambda w: w["avg_score"], reverse=True)
    return windows


def recommendation_text(windows: list[dict], origin: pd.Timestamp) -> str:
    if not windows:
        return "No standout windows in the next 48h — price and renewable share are fairly flat."
    best       = windows[0]
    hours_away = (best["start"] - origin).total_seconds() / 3600
    summary    = (f"{best['duration_h']}h, avg {best['avg_price']:.0f} EUR/MWh, "
                  f"{best['avg_renewable_share']:.0%} renewable")
    if hours_away <= 1:
        return f"Charge now — good window through {best['end']:%a %H:%M} ({summary})."
    return (f"Wait ~{hours_away:.0f}h — best window starts {best['start']:%a %H:%M}, "
            f"runs {summary}.")


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def plot_recommendation(scored_df: pd.DataFrame, windows: list[dict], origin: pd.Timestamp) -> Path:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    axes[0].plot(scored_df["timestamp"], scored_df["price_forecast"],
                 color=PALETTE["xgboost"], linewidth=1.8, label="Price forecast (blended)")
    axes[0].set_ylabel("EUR/MWh")
    axes[0].set_title(
        f"Next 48h forecast with recommended charging windows (as of {origin:%a %Y-%m-%d %H:%M})"
    )

    axes[1].plot(scored_df["timestamp"], scored_df["renewable_share_forecast"],
                 color=PALETTE["seasonal_naive_168h"], linewidth=1.8, label="Renewable share forecast")
    axes[1].set_ylabel("renewable / load")
    axes[1].set_xlabel("time")

    for w in windows:
        for ax in axes:
            ax.axvspan(w["start"], w["end"], color="#0ca30c", alpha=0.15)

    for ax in axes:
        ax.grid(True, axis="y", color="#e1e0d9", linewidth=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.legend(frameon=False, loc="upper right")

    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%a %H:%M"))
    fig.autofmt_xdate()
    plt.tight_layout()
    out = RECS_DIR / "next_48h_recommendation.png"
    plt.savefig(out, dpi=130)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="Cost vs. green weighting: 0 = cheapest only, 1 = greenest only")
    parser.add_argument("--top", type=int, default=3, help="Number of windows to report")
    parser.add_argument("--top-frac", type=float, default=0.25,
                        help="Fraction of the 48h treated as 'good' before window merging")
    args = parser.parse_args()

    forecast_df, origin = build_forecast()
    scored_df  = score_windows(forecast_df, alpha=args.alpha)
    windows    = find_windows(scored_df, top_frac=args.top_frac)[:args.top]

    logger.info(recommendation_text(windows, origin))
    for i, w in enumerate(windows, 1):
        logger.info("  #%d: %s -> %s (%dh, avg %.1f EUR/MWh, %.0f%% renewable, score %.2f)",
                    i, w["start"], w["end"], w["duration_h"],
                    w["avg_price"], w["avg_renewable_share"] * 100, w["avg_score"])

    scored_df.to_csv(RECS_DIR / "next_48h_forecast.csv", index=False)
    with open(RECS_DIR / "next_48h_windows.json", "w") as f:
        json.dump({
            "origin":         str(origin),
            "alpha":          args.alpha,
            "recommendation": recommendation_text(windows, origin),
            "windows":        [{**w, "start": str(w["start"]), "end": str(w["end"])} for w in windows],
        }, f, indent=2)

    logger.info("Saved %s", plot_recommendation(scored_df, windows, origin))


if __name__ == "__main__":
    main()
