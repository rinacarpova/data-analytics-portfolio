# Annual Revenue Plan by Segment
#
# Builds a 12-month revenue plan by business segment from public Online Retail II data.
# The project is inspired by real-world financial planning workflows in advertising monetisation.

import importlib.util
import subprocess
import sys
from pathlib import Path
import io
import zipfile
import urllib.request

REQUIRED = {
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "openpyxl": "openpyxl",
    "xlsxwriter": "xlsxwriter",
}
missing = [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# --- Parameters -------------------------------------------------------------
PLAN_START = "auto"
PLAN_MONTHS = 12
YOY_TARGET = 1.25
ORGANIC_GROWTH = "auto"
DIRECT_SALES = [15_000] * PLAN_MONTHS

SEGMENTS = ["UK", "EU", "RoW"]
MANUAL_SEGMENT = "Direct_Sales"

EU_COUNTRIES = {
    "Austria", "Belgium", "Cyprus", "Czech Republic", "Denmark", "EIRE", "Finland",
    "France", "Germany", "Greece", "Italy", "Lithuania", "Malta", "Netherlands",
    "Poland", "Portugal", "Spain", "Sweden", "European Community",
}

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
MIRROR_URL = (
    "https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/"
    "master/data/retail-data/all/online-retail-dataset.csv"
)
CACHE = DATA_DIR / "daily_revenue.csv"

NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES",
    "AMAZONFEE", "CRUK", "PADS", "ADJUST", "ADJUST2", "TEST001", "TEST002"
}


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def load_raw() -> pd.DataFrame:
    try:
        archive = zipfile.ZipFile(io.BytesIO(_download(UCI_URL)))
        xlsx = next(name for name in archive.namelist() if name.endswith(".xlsx"))
        sheets = pd.read_excel(
            archive.open(xlsx),
            sheet_name=None,
            dtype={"Invoice": str, "StockCode": str},
        )
        raw = pd.concat(sheets.values(), ignore_index=True)
        print(f"Loaded Online Retail II from UCI: {len(raw):,} rows")
    except Exception as exc:
        print(f"UCI download failed ({exc!r}); using the public mirror")
        raw = pd.read_csv(
            io.BytesIO(_download(MIRROR_URL)),
            dtype={"InvoiceNo": str, "StockCode": str},
        )
        raw = raw.rename(
            columns={
                "InvoiceNo": "Invoice",
                "UnitPrice": "Price",
                "CustomerID": "Customer ID",
            }
        )
        print(f"Loaded Online Retail from mirror: {len(raw):,} rows")
    return raw


def to_segment(country: pd.Series) -> pd.Series:
    return np.select(
        [country.eq("United Kingdom"), country.isin(EU_COUNTRIES)],
        ["UK", "EU"],
        default="RoW",
    )


def build_daily(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.drop_duplicates().copy()
    df["Invoice"] = df["Invoice"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str).str.upper()
    df = df[
        ~df["Invoice"].str.startswith("C")
        & (df["Quantity"] > 0)
        & (df["Price"] > 0)
        & ~df["StockCode"].isin(NON_PRODUCT_CODES)
    ]
    df["date"] = pd.to_datetime(df["InvoiceDate"]).dt.normalize()
    df["segment"] = to_segment(df["Country"])
    df["revenue"] = df["Quantity"] * df["Price"]
    return df.groupby(["date", "segment"], as_index=False)["revenue"].sum()


if CACHE.exists():
    daily = pd.read_csv(CACHE, parse_dates=["date"])
else:
    daily = build_daily(load_raw())
    daily.to_csv(CACHE, index=False)

print(f"{daily['date'].min():%Y-%m-%d} → {daily['date'].max():%Y-%m-%d}, {len(daily):,} rows")

# --- Monthly history --------------------------------------------------------
monthly = (
    daily.assign(month=daily["date"].dt.to_period("M").dt.to_timestamp())
    .pivot_table(index="month", columns="segment", values="revenue", aggfunc="sum", fill_value=0)
    [SEGMENTS]
)
monthly["total"] = monthly.sum(axis=1)

last_day = daily["date"].max()
last_complete_month = (
    (last_day + pd.Timedelta(days=1)).to_period("M").to_timestamp()
    - pd.offsets.MonthBegin(1)
)
monthly = monthly[monthly.index <= last_complete_month]

# --- Plan horizon and organic growth ---------------------------------------
start = (
    last_complete_month + pd.offsets.MonthBegin(1)
    if PLAN_START == "auto"
    else pd.Timestamp(PLAN_START)
)
plan_months = pd.date_range(start, periods=PLAN_MONTHS, freq="MS")

if ORGANIC_GROWTH == "auto":
    if len(monthly) >= 24:
        organic_growth = (
            monthly["total"].iloc[-12:].sum()
            / monthly["total"].iloc[-24:-12].sum()
        )
    else:
        organic_growth = 1.0
        print(
            f"Warning: only {len(monthly)} complete months of history; "
            "24 are needed to estimate organic growth. Using 1.0."
        )
else:
    organic_growth = float(ORGANIC_GROWTH)


def base_for(month: pd.Timestamp) -> dict:
    same_month = monthly[monthly.index.month == month.month]
    if same_month.empty:
        raise ValueError(f"No history for calendar month {month.month}")

    source_month = same_month.index.max()
    lag_years = month.year - source_month.year
    row = {
        "dt": month,
        "source_month": source_month,
        "lag_years": lag_years,
        "last_actual": same_month.loc[source_month, "total"],
        "base_from_history": (
            same_month.loc[source_month, "total"] * organic_growth ** lag_years
        ),
    }
    for segment in SEGMENTS:
        row[f"{segment}_last_actual"] = same_month.loc[source_month, segment]
    return row


base = pd.DataFrame([base_for(month) for month in plan_months])

# --- Base by segment --------------------------------------------------------
plan = pd.DataFrame({"dt": plan_months})
growth_factor = organic_growth ** base["lag_years"]

for segment in SEGMENTS:
    plan[f"{segment}_base"] = (
        base[f"{segment}_last_actual"] * growth_factor
    ).round()

programmatic_base = plan[[f"{segment}_base" for segment in SEGMENTS]].sum(axis=1)
plan[f"{MANUAL_SEGMENT}_base"] = DIRECT_SALES
plan["base"] = programmatic_base + plan[f"{MANUAL_SEGMENT}_base"]

last_year_factor = organic_growth ** (base["lag_years"] - 1)
last_year_total = sum(
    (base[f"{segment}_last_actual"] * last_year_factor).round().sum()
    for segment in SEGMENTS
)
reference_period = (
    f"{plan_months[0] - pd.DateOffset(years=1):%Y-%m} – "
    f"{plan_months[-1] - pd.DateOffset(years=1):%Y-%m}"
)

# --- Uplift -----------------------------------------------------------------
total_uplift = last_year_total * YOY_TARGET - programmatic_base.sum()
if total_uplift < 0:
    print("Warning: organic growth alone is above the YoY target.")

uplift_rate = total_uplift / programmatic_base.sum()
action = (programmatic_base * uplift_rate).round()
action.iloc[-1] += round(total_uplift) - action.sum()

for segment in SEGMENTS[:-1]:
    plan[f"{segment}_action"] = (plan[f"{segment}_base"] * uplift_rate).round()

plan[f"{SEGMENTS[-1]}_action"] = (
    action
    - plan[[f"{segment}_action" for segment in SEGMENTS[:-1]]].sum(axis=1)
)

for segment in SEGMENTS:
    plan[f"{segment}_total"] = plan[f"{segment}_base"] + plan[f"{segment}_action"]

plan[f"{MANUAL_SEGMENT}_action"] = 0
plan[f"{MANUAL_SEGMENT}_total"] = plan[f"{MANUAL_SEGMENT}_base"]
plan["action"] = action
plan["plan"] = plan["base"] + plan["action"]

# --- Final plan -------------------------------------------------------------
all_segments = SEGMENTS + [MANUAL_SEGMENT]
columns = ["dt", "plan", "base", "action"] + [
    f"{segment}_{kind}"
    for segment in all_segments
    for kind in ("total", "base", "action")
]
plan = plan[columns]

# --- Sanity checks ----------------------------------------------------------
segment_totals = plan[[f"{segment}_total" for segment in all_segments]].sum(axis=1)
assert (segment_totals == plan["plan"]).all(), "Segments do not add up to plan"
assert (plan["plan"] == plan["base"] + plan["action"]).all()
assert (
    plan[[f"{segment}_base" for segment in all_segments]].sum(axis=1)
    == plan["base"]
).all()

programmatic_plan = plan["plan"] - plan[f"{MANUAL_SEGMENT}_total"]
achieved_yoy = programmatic_plan.sum() / last_year_total
assert abs(achieved_yoy - YOY_TARGET) < 1e-6, achieved_yoy

print("Programmatic, GBP")
print(f"  Previous 12 months: {last_year_total:>14,.0f}")
print(f"  Organic growth:     {programmatic_base.sum() - last_year_total:>14,.0f}")
print(f"  Initiatives uplift: {plan['action'].sum():>14,.0f}")
print(
    f"  Plan:               {programmatic_plan.sum():>14,.0f} "
    f"(YoY {achieved_yoy:.3f}, target {YOY_TARGET})"
)
print(f"Direct Sales:         {plan[f'{MANUAL_SEGMENT}_total'].sum():>14,.0f}")
print(f"Total plan:           {plan['plan'].sum():>14,.0f}")
print("All checks passed ✓")

# --- Visualisation ----------------------------------------------------------
fig, axes = plt.subplots(
    1,
    2,
    figsize=(15, 4.8),
    gridspec_kw={"width_ratios": [1.4, 1]},
)
fmt_k = mtick.FuncFormatter(lambda x, _: f"{x / 1e3:,.0f}k")

ax = axes[0]
ax.plot(monthly.index, monthly["total"], lw=2, label="Actual")
ax.plot(
    plan["dt"],
    programmatic_base,
    lw=2,
    ls="--",
    label=f"Base (organic growth ×{organic_growth:.3f})",
)
ax.plot(
    plan["dt"],
    programmatic_plan,
    lw=2.5,
    label=f"Plan (YoY ×{YOY_TARGET})",
)
ax.set_title("Programmatic revenue, GBP: history and plan", loc="left", fontweight="bold")
ax.yaxis.set_major_formatter(fmt_k)
ax.legend(frameon=False)

ax = axes[1]
bottom = np.zeros(PLAN_MONTHS)
labels = plan["dt"].dt.strftime("%b\n%y")
for segment in all_segments:
    ax.bar(labels, plan[f"{segment}_total"], bottom=bottom, label=segment.replace("_", " "))
    bottom += plan[f"{segment}_total"].to_numpy()

ax.set_title("Plan by segment, GBP", loc="left", fontweight="bold")
ax.yaxis.set_major_formatter(fmt_k)
ax.legend(frameon=False, ncol=2, fontsize=9)

for axis in axes:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", alpha=0.3)

plt.tight_layout()
fig.savefig(OUTPUT_DIR / "plan_overview.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# --- Export to Excel --------------------------------------------------------
period = f"{plan_months[0]:%Y-%m}_{plan_months[-1]:%Y-%m}"
xlsx_path = OUTPUT_DIR / f"revenue_plan_{period}.xlsx"

with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
    workbook = writer.book
    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "white",
            "bg_color": "#2F3E52",
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "border": 1,
        }
    )
    number = workbook.add_format({"num_format": "#,##0", "border": 1})
    date_format = workbook.add_format(
        {
            "num_format": "[$-409]mmm yyyy",
            "border": 1,
            "align": "center",
        }
    )
    total_format = workbook.add_format(
        {
            "num_format": "#,##0",
            "border": 1,
            "bold": True,
            "bg_color": "#EDEFF2",
        }
    )

    worksheet = workbook.add_worksheet("Plan")
    writer.sheets["Plan"] = worksheet

    for column_index, column in enumerate(columns):
        worksheet.write(0, column_index, column.replace("_", " "), header)

    for row_index, row in enumerate(plan.itertuples(index=False), start=1):
        worksheet.write_datetime(row_index, 0, row[0].to_pydatetime(), date_format)
        for column_index, value in enumerate(row[1:], start=1):
            worksheet.write_number(row_index, column_index, float(value), number)

    total_row_index = len(plan) + 1
    worksheet.write(total_row_index, 0, "TOTAL", total_format)

    for column_index, column in enumerate(columns[1:], start=1):
        if column_index < 26:
            letter = chr(ord("A") + column_index)
        else:
            letter = "A" + chr(ord("A") + column_index - 26)

        worksheet.write_formula(
            total_row_index,
            column_index,
            f"=SUM({letter}2:{letter}{total_row_index})",
            total_format,
            float(plan[column].sum()),
        )

    worksheet.set_row(0, 32)
    worksheet.set_column(0, 0, 11)
    worksheet.set_column(1, len(columns) - 1, 13)
    worksheet.freeze_panes(1, 1)

    assumptions = pd.DataFrame(
        {
            "parameter": [
                "Revenue",
                "Plan period",
                "Reference period (YoY)",
                "YoY target",
                "Organic growth per year",
                "Uplift on top of base",
            ],
            "value": [
                "gross, GBP",
                f"{plan_months[0]:%Y-%m} – {plan_months[-1]:%Y-%m}",
                reference_period,
                YOY_TARGET,
                round(organic_growth, 4),
                f"{uplift_rate:.2%}",
            ],
        }
    )
    assumptions.to_excel(writer, sheet_name="Assumptions", index=False)

    history = monthly.reset_index()
    history["month"] = history["month"].dt.strftime("%Y-%m")
    history.round(0).to_excel(writer, sheet_name="History", index=False)

print(f"Saved → {xlsx_path}")
