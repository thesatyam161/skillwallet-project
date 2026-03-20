import os
import sqlite3

import pandas as pd
from paths import DB_PATH, UPLOAD_DIR

REQUIRED_COLUMNS = [
    "Product ID",
    "Product Category",
    "Product Position",
    "Price",
    "Promotion",
    "Foot Traffic",
    "Consumer Demographics",
    "Seasonal",
    "Competitor Price",
    "Sales Volume",
]

COLUMN_ALIASES = {
    "Product ID": ["product id", "product_id"],
    "Product Category": ["product category", "category", "product_category"],
    "Product Position": ["product position", "position", "store placement", "product_position"],
    "Price": ["price", "unit price", "product price"],
    "Promotion": ["promotion", "promoted", "promotion status"],
    "Foot Traffic": ["foot traffic", "traffic", "store traffic", "foot_traffic"],
    "Consumer Demographics": ["consumer demographics", "demographics", "customer demographics", "consumer_demographics"],
    "Seasonal": ["seasonal", "seasonality"],
    "Competitor Price": ["competitor price", "competitor's price", "competitor_price", "competitor price "],
    "Sales Volume": ["sales volume", "units sold", "sales", "sales_volume"],
}

BOOLEAN_MAP = {
    "yes": True,
    "no": False,
    "true": True,
    "false": False,
    "1": True,
    "0": False,
}


def _normalize_column_name(name):
    return str(name).strip().lower().replace("_", " ")


def _canonicalize_columns(df):
    renamed = {}
    normalized_to_actual = {_normalize_column_name(column): column for column in df.columns}

    for canonical, aliases in COLUMN_ALIASES.items():
        candidates = [_normalize_column_name(canonical), *aliases]
        for alias in candidates:
            actual = normalized_to_actual.get(alias)
            if actual and actual != canonical:
                renamed[actual] = canonical
                break

    if renamed:
        df = df.rename(columns=renamed)

    if "Competitor Price" not in df.columns and "Price" in df.columns:
        price_series = pd.to_numeric(df["Price"], errors="coerce")
        df["Competitor Price"] = price_series

    return df


def _clean_boolean(series):
    normalized = series.astype(str).str.strip().str.lower()
    mapped = normalized.map(BOOLEAN_MAP)
    if mapped.isna().any():
        invalid = sorted(series[mapped.isna()].dropna().astype(str).unique())
        raise ValueError(
            "Invalid values found in boolean column. Use only Yes/No, True/False, or 1/0 values: "
            + ", ".join(invalid[:5])
        )
    return mapped.fillna(False).astype(bool)


def process_data(csv_file_path):
    try:
        df = pd.read_csv(csv_file_path)
    except Exception as exc:
        raise ValueError(f"Could not read the CSV file: {exc}") from exc

    df = _canonicalize_columns(df)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(
            "Dataset schema is incomplete. Missing columns: " + ", ".join(missing_columns)
        )

    df = df[REQUIRED_COLUMNS].copy()

    for column in ["Price", "Competitor Price", "Sales Volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    text_columns = [
        "Product ID",
        "Product Category",
        "Product Position",
        "Foot Traffic",
        "Consumer Demographics",
    ]
    for column in text_columns:
        df[column] = df[column].replace("", pd.NA).fillna(df[column].mode().iloc[0]).astype(str).str.strip()

    for column in ["Price", "Competitor Price", "Sales Volume"]:
        df[column] = df[column].fillna(df[column].median())

    df["Promotion"] = _clean_boolean(df["Promotion"].fillna("No"))
    df["Seasonal"] = _clean_boolean(df["Seasonal"].fillna("No"))

    df["Price Difference"] = (df["Price"] - df["Competitor Price"]).round(2)
    df["Traffic Weight"] = df["Foot Traffic"].map({"Low": 1, "Medium": 2, "High": 3}).fillna(2).astype(int)
    df["Traffic Conversion Index"] = (df["Sales Volume"] / df["Traffic Weight"]).round(2)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    df.to_sql("retail_sales", conn, if_exists="replace", index=False)
    conn.close()

    clean_csv_path = os.path.join(UPLOAD_DIR, "cleaned_retail_data_for_tableau.csv")
    df.to_csv(clean_csv_path, index=False)

    return df


if __name__ == "__main__":
    raw_file = os.path.join(UPLOAD_DIR, "raw_retail_data.csv")
    if os.path.exists(raw_file):
        process_data(raw_file)
    else:
        print(f"Raw file {raw_file} not found. Please run data_generator.py first.")
