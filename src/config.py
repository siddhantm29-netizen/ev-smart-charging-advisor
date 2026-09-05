"""Shared configuration and path constants for the EV Smart-Charging Advisor."""

from pathlib import Path

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT      = Path(__file__).resolve().parent.parent
RAW_DATA_DIR      = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- SMARD (Bundesnetzagentur electricity market data) -----------------------
# Docs: https://smard.api.bund.dev
SMARD_BASE_URL = "https://www.smard.de/app"

# Each entry: {"filter": <SMARD filter id>, "region": <SMARD region code>}.
# Generation/consumption use region "DE"; the day-ahead price is quoted for "DE-LU".
SMARD_FILTERS = {
    "price_eur_mwh":     {"filter": 4169, "region": "DE-LU"},  # Marktpreis
    "load_mw":           {"filter":  410, "region": "DE"},     # Stromverbrauch (Netzlast)
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

# --- Ladesäulenregister (public charging stations) ---------------------------
# The Bundesnetzagentur-hosted FeatureServer now requires a token for anonymous
# requests. We pull from Esri Deutschland's public open-data mirror instead —
# same dataset/license (refreshed monthly), no token needed.
LADESTATIONEN_URL = (
    "https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/"
    "Ladesaeulen_in_Deutschland/FeatureServer/0/query"
)

# Bounding box for Germany, WGS84 lon/lat: (xmin, ymin, xmax, ymax)
GERMANY_BBOX = (5.6, 47.2, 15.2, 55.1)