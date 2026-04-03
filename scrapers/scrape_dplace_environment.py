"""
Scrape environmental variables for EA societies from D-PLACE GitHub data.

Sources:
  EA societies (IDs + coords):
    datasets/EA/societies.csv
  Precipitation (via SCCS cross-reference):
    datasets/SCCS/societies.csv
    datasets/ecoClimate/data.csv
      var_ids: MonthlyMeanPrecipitation, AnnualPrecipitationVariance
  Net primary productivity / predictability (via Binford cross-reference):
    datasets/Binford/societies.csv
    datasets/MODIS/data.csv
      var_ids: MonthlyMeanNetPrimaryProduction, NetPrimaryProductionPredictability

Note: Temperature variables (mean_temperature, variance_temperature) are not
available in the D-PLACE ecoClimate or MODIS datasets and will be output as NaN.

Output: outputs/dplace/dplace_environment.csv
"""

import io
import os

import pandas as pd
import requests

BASE = "https://raw.githubusercontent.com/D-PLACE/dplace-data/master/datasets"

URLS = {
    "ea_societies":       f"{BASE}/EA/societies.csv",
    "sccs_societies":     f"{BASE}/SCCS/societies.csv",
    "binford_societies":  f"{BASE}/Binford/societies.csv",
    "ecoclimate_data":    f"{BASE}/ecoClimate/data.csv",
    "modis_data":         f"{BASE}/MODIS/data.csv",
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "outputs", "dplace", "dplace_environment.csv"
)

ECOCLIMATE_VARS = {
    "MonthlyMeanPrecipitation":   "mean_precipitation",
    "AnnualPrecipitationVariance": "variance_precipitation",
}

MODIS_VARS = {
    "MonthlyMeanNetPrimaryProduction":  "net_primary_productivity",
    "NetPrimaryProductionPredictability": "environmental_predictability",
}

OUTPUT_COLS = [
    "soc_id",
    "pref_name_for_society",
    "Lat",
    "Long",
    "mean_temperature",
    "variance_temperature",
    "mean_precipitation",
    "variance_precipitation",
    "net_primary_productivity",
    "environmental_predictability",
]


def fetch_csv(url):
    print(f"  Fetching {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def pivot_vars(data_df, var_map):
    """Filter data_df to the requested var_ids and pivot to wide format."""
    subset = data_df[data_df["var_id"].isin(var_map)][["soc_id", "var_id", "code"]].copy()
    wide = subset.pivot_table(index="soc_id", columns="var_id", values="code", aggfunc="first")
    wide = wide.rename(columns=var_map)
    wide = wide.reset_index()
    return wide


def build_xd_lookup(societies_df):
    """Return {xd_id -> dataset_specific_id} from a societies dataframe."""
    return dict(zip(societies_df["xd_id"], societies_df["id"]))


def main():
    print("Loading source data...")
    ea       = fetch_csv(URLS["ea_societies"])
    sccs     = fetch_csv(URLS["sccs_societies"])
    binford  = fetch_csv(URLS["binford_societies"])
    eco_data = fetch_csv(URLS["ecoclimate_data"])
    modis    = fetch_csv(URLS["modis_data"])

    # Cross-reference lookups: xd_id -> dataset-specific soc_id
    xd_to_sccs    = build_xd_lookup(sccs)
    xd_to_binford = build_xd_lookup(binford)

    ea["sccs_id"]    = ea["xd_id"].map(xd_to_sccs)
    ea["binford_id"] = ea["xd_id"].map(xd_to_binford)

    # Pivot environmental data to wide format
    eco_wide   = pivot_vars(eco_data, ECOCLIMATE_VARS)
    modis_wide = pivot_vars(modis, MODIS_VARS)

    # Join precipitation onto EA via SCCS cross-reference
    ea = ea.merge(
        eco_wide.rename(columns={"soc_id": "sccs_id"}),
        on="sccs_id",
        how="left",
    )

    # Join NPP / predictability onto EA via Binford cross-reference
    ea = ea.merge(
        modis_wide.rename(columns={"soc_id": "binford_id"}),
        on="binford_id",
        how="left",
    )

    # Temperature variables are not available in these datasets
    ea["mean_temperature"]     = float("nan")
    ea["variance_temperature"] = float("nan")

    out = ea.rename(columns={"id": "soc_id"})[OUTPUT_COLS]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)

    matched_eco   = out["mean_precipitation"].notna().sum()
    matched_modis = out["net_primary_productivity"].notna().sum()
    print(f"\nDone. {len(out)} EA societies written to {OUTPUT_PATH}")
    print(f"  Precipitation matched: {matched_eco}/{len(out)}")
    print(f"  NPP matched:           {matched_modis}/{len(out)}")
    print("  Temperature:           not available in source data (NaN)")


if __name__ == "__main__":
    main()
