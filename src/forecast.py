"""
forecast.py — Phase 3 of the roadmap: forecast next 24-48h electricity price
and renewable-share, comparing a direct multi-horizon XGBoost model against a
Prophet baseline, backtested on held-out recent data.

Usage:
    python src/forecast.py --target price
    python src/forecast.py --target renewable_share
    python src/forecast.py --target price --no-prophet   # skip the (slower) Prophet baseline
    python src/forecast.py --summary                     # combined skill-score chart across both targets
                                                           # (run both --target backtests first)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from config import PROCESSED_DATA_DIR, PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BASE_SERIES = ["price_eur_mwh", "renewable_share", "load_mw"]
LAGS = [1, 2, 3, 24, 48, 168]           # hours: recent, daily, weekly
ROLLING_WINDOWS = [24, 168]              # hours
MAX_HORIZON = 48                         # forecast next 48h, per the roadmap
HORIZONS = list(range(1, MAX_HORIZON + 1))

# Fixed color-per-entity assignment (never per-rank) — same hue for the same
# method across every chart. Ordering follows the project's validated
# categorical palette; "persistence" (yellow, slot 4) is kept away from
# "prophet" (orange, slot 2) in bar-chart order since that adjacent pair is
# the one flagged as CVD-risky in the palette reference.
PALETTE = {
    "actual": "#0b0b0b",
    "xgboost": "#2a78d6",
    "prophet": "#eb6834",
    "seasonal_naive_168h": "#1baf7a",
    "persistence_naive": "#eda100",
}
LABELS = {
    "actual": "Actual",
    "xgboost": "XGBoost",
    "prophet": "Prophet",
    "seasonal_naive_168h": "Seasonal naive (t-168h)",
    "persistence_naive": "Persistence naive",
}


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def load_clean_smard() -> pd.DataFrame:
    path = PROCESSED_DATA_DIR / "smard_market_data_clean.csv"
    df = pd.read_csv(path, parse_dates=["datetime"])
    df = df.set_index("datetime").sort_index()
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    idx = df.index
    df["hour_sin"] = np.sin(2 * np.pi * idx.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * idx.hour / 24)
    df["dow_sin"] = np.sin(2 * np.pi * idx.dayofweek / 7)
    df["dow_cos"] = np.cos(2 * np.pi * idx.dayofweek / 7)
    df["month_sin"] = np.sin(2 * np.pi * idx.month / 12)
    df["month_cos"] = np.cos(2 * np.pi * idx.month / 12)
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    return df


def add_lag_rolling_features(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        for lag in LAGS:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)
        for w in ROLLING_WINDOWS:
            shifted = df[col].shift(1)  # never include the current hour in its own rolling stat
            df[f"{col}_roll_mean{w}"] = shifted.rolling(w).mean()
            df[f"{col}_roll_std{w}"] = shifted.rolling(w).std()
    return df


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar + lag/rolling features for all base series. Drops the
    warm-up rows at the start where the longest lag/rolling window isn't
    full yet."""
    feat = add_calendar_features(df)
    feat = add_lag_rolling_features(feat, BASE_SERIES)
    warmup = max(LAGS + ROLLING_WINDOWS)
    return feat.iloc[warmup:].copy()


def feature_columns(feat_df: pd.DataFrame) -> list:
    exclude = set(BASE_SERIES) | {"renewable_mw"}
    return [c for c in feat_df.columns if c not in exclude]


def make_horizon_dataset(feat_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """
    Direct multi-horizon dataset: one row per (origin timestamp, horizon),
    with features as known at the origin and 'y' = target value `horizon`
    hours later. A single model trained on this pooled dataset (with
    `horizon` as a feature) predicts any of the next MAX_HORIZON hours
    directly from one feature vector — no recursive one-step-ahead
    compounding of forecast error.
    """
    fcols = feature_columns(feat_df)
    target = feat_df[target_col]
    chunks = []
    for h in HORIZONS:
        chunk = feat_df[fcols].copy()
        chunk["horizon"] = h
        chunk["origin"] = feat_df.index
        chunk["y"] = target.shift(-h).values
        chunks.append(chunk)
    long_df = pd.concat(chunks, ignore_index=True)
    return long_df.dropna(subset=["y"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# XGBoost — direct multi-horizon model
# ---------------------------------------------------------------------------

def train_xgboost(train_df: pd.DataFrame, feature_cols: list) -> XGBRegressor:
    model = XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        n_jobs=-1,
    )
    model.fit(train_df[feature_cols + ["horizon"]], train_df["y"])
    return model


def forecast_xgboost(model: XGBRegressor, origin_features: pd.Series, feature_cols: list) -> pd.Series:
    """Predict all MAX_HORIZON steps ahead from a single origin's feature row."""
    rows = pd.DataFrame([origin_features[feature_cols]] * len(HORIZONS))
    rows["horizon"] = HORIZONS
    preds = model.predict(rows[feature_cols + ["horizon"]])
    return pd.Series(preds, index=HORIZONS)


# ---------------------------------------------------------------------------
# Prophet — univariate baseline
# ---------------------------------------------------------------------------

def train_prophet(train_series: pd.Series):
    from prophet import Prophet

    prophet_df = pd.DataFrame({
        "ds": train_series.index.tz_localize(None),
        "y": train_series.values,
    })
    model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
    model.fit(prophet_df)
    return model


def forecast_prophet(model, cutoff, horizons=HORIZONS) -> pd.Series:
    future = pd.DataFrame({
        "ds": [cutoff.tz_localize(None) + pd.Timedelta(hours=h) for h in horizons]
    })
    fc = model.predict(future)
    return pd.Series(fc["yhat"].values, index=horizons)


# ---------------------------------------------------------------------------
# Baselines — the benchmark any "real" model has to beat
# ---------------------------------------------------------------------------

def baseline_persistence(df: pd.DataFrame, cutoff: pd.Timestamp, target_col: str) -> pd.Series:
    """Naive: 'it'll stay whatever it is right now.' The weakest defensible
    baseline — if a model can't beat this, it isn't adding value."""
    last_val = df.loc[cutoff, target_col]
    return pd.Series([last_val] * len(HORIZONS), index=HORIZONS)


def baseline_seasonal_naive(df: pd.DataFrame, cutoff: pd.Timestamp, target_col: str, lag_hours: int = 168) -> pd.Series:
    """Seasonal naive: 'it'll be whatever it was at this same hour last week.'
    lag_hours=168 (1 week) is used rather than 24h so that every horizon up to
    MAX_HORIZON=48 always references a timestamp at or before the cutoff
    (i.e. genuinely known at forecast time, never the forecast window itself).
    This is the standard, much harder-to-beat benchmark for hourly electricity
    series, since it captures both daily and day-of-week patterns for free."""
    idx = [cutoff + pd.Timedelta(hours=h - lag_hours) for h in HORIZONS]
    return pd.Series(df.loc[idx, target_col].values, index=HORIZONS)


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def backtest(target_col: str, use_prophet: bool = True) -> dict:
    df = load_clean_smard()
    feat_df = build_feature_frame(df)
    fcols = feature_columns(feat_df)

    cutoff = feat_df.index[-1] - pd.Timedelta(hours=MAX_HORIZON)
    logger.info("Backtest cutoff: %s (holding out the last %dh)", cutoff, MAX_HORIZON)

    long_df = make_horizon_dataset(feat_df, target_col)
    train_long = long_df[long_df["origin"] <= cutoff]

    logger.info("Training XGBoost on %d pooled (origin, horizon) rows", len(train_long))
    xgb_model = train_xgboost(train_long, fcols)

    origin_row = feat_df.loc[cutoff]
    xgb_preds = forecast_xgboost(xgb_model, origin_row, fcols)

    actual = df.loc[[cutoff + pd.Timedelta(hours=h) for h in HORIZONS], target_col]
    actual.index = HORIZONS

    persistence_preds = baseline_persistence(df, cutoff, target_col)
    seasonal_preds = baseline_seasonal_naive(df, cutoff, target_col)

    def _metrics(preds):
        return {
            "mae": mean_absolute_error(actual, preds),
            "rmse": mean_squared_error(actual, preds) ** 0.5,
        }

    results = {
        "target": target_col,
        "cutoff": str(cutoff),
        "persistence_naive": _metrics(persistence_preds),
        "seasonal_naive_168h": _metrics(seasonal_preds),
        "xgboost": _metrics(xgb_preds),
    }

    xgb_model.save_model(str(MODELS_DIR / f"xgboost_{target_col}.json"))

    preds_df = pd.DataFrame({
        "horizon": HORIZONS,
        "actual": actual.values,
        "persistence_naive": persistence_preds.values,
        "seasonal_naive_168h": seasonal_preds.values,
        "xgboost": xgb_preds.values,
    })

    if use_prophet:
        train_series = df.loc[df.index <= cutoff, target_col]
        logger.info("Training Prophet on %d rows", len(train_series))
        prophet_model = train_prophet(train_series)
        prophet_preds = forecast_prophet(prophet_model, cutoff)
        results["prophet"] = _metrics(prophet_preds)
        preds_df["prophet"] = prophet_preds.values

        from prophet.serialize import model_to_json
        with open(MODELS_DIR / f"prophet_{target_col}.json", "w") as f:
            f.write(model_to_json(prophet_model))

    # Skill score relative to the seasonal-naive benchmark (the harder,
    # more meaningful baseline to beat): fraction of its MAE we cut. 0 =
    # no better than the benchmark; negative = worse than it.
    benchmark_mae = results["seasonal_naive_168h"]["mae"]
    for name in ("xgboost", "prophet"):
        if name in results:
            results[name]["skill_vs_seasonal_naive"] = 1 - results[name]["mae"] / benchmark_mae

    preds_df.to_csv(MODELS_DIR / f"backtest_{target_col}.csv", index=False)
    with open(MODELS_DIR / f"backtest_{target_col}_metrics.json", "w") as f:
        json.dump(results, f, indent=2)

    plot_backtest_timeseries(preds_df, target_col)
    plot_metrics_bar(results, target_col)

    return results


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _style_axes(ax) -> None:
    ax.grid(True, axis="y", color="#e1e0d9", linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#c3c2b7")
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")


def _target_label(target_col: str) -> str:
    return "EUR/MWh" if target_col == "price_eur_mwh" else "renewable / load"


def plot_backtest_timeseries(preds_df: pd.DataFrame, target_col: str) -> Path:
    """Actual vs. each forecast method over the 48h holdout. Persistence is
    left off this one on purpose — with 5 lines on one chart plus a
    fast-moving actual series, it mostly adds clutter; it's still in the bar
    chart and the metrics table."""
    import matplotlib.pyplot as plt

    ylabel = _target_label(target_col)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(preds_df["horizon"], preds_df["actual"], color=PALETTE["actual"],
            linewidth=2.2, label=LABELS["actual"], zorder=5)
    for col in ("seasonal_naive_168h", "prophet", "xgboost"):
        if col in preds_df.columns:
            ax.plot(preds_df["horizon"], preds_df[col], color=PALETTE[col],
                     linewidth=1.6, label=LABELS[col])
    if target_col == "price_eur_mwh":
        ax.axhline(0, color="#c3c2b7", linewidth=0.8)
    ax.set_xlabel("hours ahead")
    ax.set_ylabel(ylabel)
    ax.set_title(f"48h backtest — {target_col}")
    _style_axes(ax)
    ax.legend(frameon=False)
    plt.tight_layout()
    out = MODELS_DIR / f"backtest_{target_col}_timeseries.png"
    plt.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_metrics_bar(results: dict, target_col: str) -> Path:
    """MAE by method, including both baselines, in a fixed color-safe order."""
    import matplotlib.pyplot as plt

    order = [m for m in ("persistence_naive", "seasonal_naive_168h", "prophet", "xgboost") if m in results]
    maes = [results[m]["mae"] for m in order]
    colors = [PALETTE[m] for m in order]
    labels = [LABELS[m] for m in order]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, maes, color=colors, width=0.55)
    for bar, mae in zip(bars, maes):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{mae:.3g}",
                 ha="center", va="bottom", fontsize=9, color="#0b0b0b")
    ax.set_ylabel(f"MAE ({_target_label(target_col)})")
    ax.set_title(f"48h backtest MAE by method — {target_col}")
    _style_axes(ax)
    plt.tight_layout()
    out = MODELS_DIR / f"backtest_{target_col}_mae_comparison.png"
    plt.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_skill_score_summary() -> Path:
    """Combined chart: XGBoost/Prophet skill (% MAE reduction) vs. the
    seasonal-naive benchmark, for both targets side by side. Requires both
    `--target price` and `--target renewable_share` to have been run first."""
    import matplotlib.pyplot as plt

    targets = ["price_eur_mwh", "renewable_share"]
    all_results = {}
    for t in targets:
        path = MODELS_DIR / f"backtest_{t}_metrics.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run `python src/forecast.py --target ...` for both targets first")
        with open(path) as f:
            all_results[t] = json.load(f)

    methods = [m for m in ("prophet", "xgboost") if m in all_results[targets[0]]]
    x = np.arange(len(targets))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for i, m in enumerate(methods):
        vals = [all_results[t][m]["skill_vs_seasonal_naive"] * 100 for t in targets]
        offset = (i - (len(methods) - 1) / 2) * width
        bars = ax.bar(x + offset, vals, width, label=LABELS[m], color=PALETTE[m])
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{v:+.0f}%",
                     ha="center", va="bottom" if v >= 0 else "top", fontsize=9, color="#0b0b0b")

    ax.axhline(0, color="#898781", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(["Price (EUR/MWh)", "Renewable share"])
    ax.set_ylabel("Skill vs. seasonal-naive benchmark (% MAE reduction)")
    ax.set_title("Forecast skill relative to the seasonal-naive benchmark")
    _style_axes(ax)
    ax.legend(frameon=False)
    plt.tight_layout()
    out = MODELS_DIR / "backtest_skill_score_summary.png"
    plt.savefig(out, dpi=130)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=["price", "renewable_share"], default="price",
                         help="Which series to forecast (default: price)")
    parser.add_argument("--no-prophet", action="store_true", help="Skip the Prophet baseline (XGBoost only)")
    parser.add_argument("--summary", action="store_true",
                         help="Skip backtesting; build the combined skill-score chart from existing results")
    args = parser.parse_args()

    if args.summary:
        out = plot_skill_score_summary()
        logger.info("Saved %s", out)
        return

    target_col = "price_eur_mwh" if args.target == "price" else "renewable_share"
    results = backtest(target_col, use_prophet=not args.no_prophet)

    logger.info("Backtest results for %s:", target_col)
    logger.info(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
