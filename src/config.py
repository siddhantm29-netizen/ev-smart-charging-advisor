"""Shared configuration and constants for the EV Smart-Charging Advisor project."""

from pathlib import Path

# --- Paths ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- SMARD (Bundesnetzagentur electricity market data) --------------------
# Docs: https://github.com/bundesAPI/smard-api
SMARD_BASE_URL = "https://www.smard.de/app"

# Each entry: {"filter": <SMARD filter id>, "region": <SMARD region code>}
# Generation/consumption use region "DE" (all of Germany); the day-ahead
# price is quoted for the "DE-LU" market area.
SMARD_FILTERS = {
    "price_eur_mwh":     {"filter": 4169, "region": "DE-LU"},  # Marktpreis: Deutschland/Luxemburg
    "load_mw":           {"filter": 410,  "region": "DE"},     # Stromverbrauch: Gesamt (Netzlast)
    "wind_onshore_mw":   {"filter": 4067, "region": "DE"},
    "wind_offshore_mw":  {"filter": 1225, "region": "DE"},
    "solar_mw":          {"filter": 4068, "region": "DE"},
    "hydro_mw":          {"filter": 1226, "region": "DE"},
    "biomass_mw":        {"filter": 4066, "region": "DE"},
    "lignite_mw":        {"filter": 1223, "region": "DE"},     # Braunkohle
    "hard_coal_mw":      {"filter": 4069, "region": "DE"},     # Steinkohle
    "natural_gas_mw":    {"filter": 4071, "region": "DE"},
    "nuclear_mw":        {"filter": 1224, "region": "DE"},
    "pumped_storage_mw": {"filter": 4070, "region": "DE"},
}

# --- Ladesäulenregister (public charging stations) ------------------------
# Docs: https://github.com/bundesAPI/ladestationen-api
# NOTE: the Bundesnetzagentur-hosted FeatureServer (services6.arcgis.com/.../
# Ladesaeulenregister/FeatureServer/7) now returns HTTP 200 with a "Token
# Required" (SB_0006) error body for anonymous requests — it was opened up
# without a token as of the doc/brief, but requires one now. We instead pull
# the same dataset (same source/license, refreshed monthly) from Esri
# Deutschland's public open-data mirror, which needs no token.
LADESTATIONEN_URL = (
    "https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/"
    "Ladesaeulen_in_Deutschland/FeatureServer/0/query"
)

# Bounding box for all of Germany, WGS84 lon/lat degrees: (xmin, ymin, xmax, ymax)
GERMANY_BBOX = (5.6, 47.2, 15.2, 55.1)