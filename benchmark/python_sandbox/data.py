from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
SALES_CSV = DATA_DIR / "sales.csv"
REGIONS_CSV = DATA_DIR / "regions.csv"

SALES_COLUMNS = [
    "order_id",
    "customer_id",
    "region_id",
    "product_category",
    "price_usd",
    "quantity",
]

REGIONS_COLUMNS = [
    "region_id",
    "region_name",
]


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
        name="shape_list",
        user_message=(
            "Use sales_df (already loaded). Return [rows, cols] as a JSON list of integers."
        ),
        expected=[int(_load_frames()[0].shape[0]), int(_load_frames()[0].shape[1])],
    ),
    Scenario(
        name="first_region_name",
        user_message=(
            "Use regions_df (already loaded). Return the first region_name as a JSON string."
        ),
        expected=str(_load_frames()[1].iloc[0]["region_name"]),
    ),
    Scenario(
        name="sum_quantity",
        user_message=(
            "Use sales_df (already loaded). Return sum(quantity) as a JSON integer."
        ),
        expected=int(_load_frames()[0]["quantity"].sum()),
    ),
    Scenario(
        name="east_region_id",
        user_message=(
            "Use regions_df (already loaded). Find region_id where region_name == \"East\". "
        ) + "Return that region_id as a JSON string.",
        expected=str(_load_frames()[1].loc[_load_frames()[1]["region_name"] == "East", "region_id"].iloc[0]),
    ),
]
