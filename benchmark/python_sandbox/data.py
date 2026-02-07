from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SALES_CSV = DATA_DIR / "sales.csv"
REGIONS_CSV = DATA_DIR / "regions.csv"


@dataclass
class Scenario:
    name: str
    user_message: str
    expected: object


def _load_frames():
    sales = pd.read_csv(SALES_CSV)
    regions = pd.read_csv(REGIONS_CSV)
    return sales, regions


def _round(value: float) -> float:
    return round(float(value), 2)


def _expected_revenue_by_region():
    sales, regions = _load_frames()
    sales["revenue"] = sales["price_usd"] * sales["quantity"]
    merged = sales.merge(regions, on="region_id", how="left")
    totals = merged.groupby("region_name")["revenue"].sum()
    return {key: _round(val) for key, val in totals.items()}


def _expected_top_customer():
    sales, _ = _load_frames()
    sales["revenue"] = sales["price_usd"] * sales["quantity"]
    totals = sales.groupby("customer_id")["revenue"].sum()
    top_id = totals.idxmax()
    return {"customer_id": top_id, "revenue": _round(totals.loc[top_id])}


def _expected_avg_computers():
    sales, _ = _load_frames()
    sales["revenue"] = sales["price_usd"] * sales["quantity"]
    computers = sales[sales["product_category"] == "Computers"]
    return _round(computers["revenue"].mean())


def _expected_east_total():
    sales, regions = _load_frames()
    sales["revenue"] = sales["price_usd"] * sales["quantity"]
    merged = sales.merge(regions, on="region_id", how="left")
    east = merged[merged["region_name"] == "East"]
    return _round(east["revenue"].sum())


SCENARIOS = [
    Scenario(
        name="revenue_by_region",
        user_message=(
            "Read /input/sales.csv and /input/regions.csv. Compute total revenue per region_name ")
        + "(price_usd * quantity). Print a JSON object mapping region_name to revenue (2 decimals).",
        expected=_expected_revenue_by_region(),
    ),
    Scenario(
        name="top_customer",
        user_message=(
            "Read /input/sales.csv. Find the customer_id with the highest total revenue ")
        + "(price_usd * quantity). Print JSON: {\"customer_id\": ..., \"revenue\": ...}.",
        expected=_expected_top_customer(),
    ),
    Scenario(
        name="avg_computers",
        user_message=(
            "Read /input/sales.csv. Compute the average order revenue for product_category == \"Computers\". ")
        + "Print a JSON number with 2 decimals.",
        expected=_expected_avg_computers(),
    ),
    Scenario(
        name="east_total",
        user_message=(
            "Read /input/sales.csv and /input/regions.csv. Join on region_id and compute total revenue ")
        + "for region_name == \"East\". Print a JSON number with 2 decimals.",
        expected=_expected_east_total(),
    ),
]
