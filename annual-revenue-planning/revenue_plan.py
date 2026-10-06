# Annual Revenue Plan by Segment
#
# Builds a 12-month revenue plan by business segment from public Online Retail II data
# and exports it to Excel. Inspired by real-world financial planning workflows in
# advertising monetisation.
#
# Single source of the planning logic. revenue_plan.ipynb imports these functions
# and walks through the same calculation step by step.
#
#   pip install -r requirements.txt
#   python revenue_plan.py

import io
import urllib.request
import zipfile
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from xlsxwriter.utility import xl_col_to_name

# --- Business inputs --------------------------------------------------------
PLAN_START = "auto"          # "auto" = month after the last complete month, or "YYYY-MM-01"
PLAN_MONTHS = 12
YOY_TARGET = 1.25            # programmatic plan / previous 12 months
ORGANIC_GROWTH = "auto"      # "auto" = last 12 months / previous 12 months, or a number
DIRECT_SALES = [15_000] * PLAN_MONTHS  # manual plan, added on top of the YoY target

SEGMENTS = ["UK", "EU", "RoW"]
MANUAL_SEGMENT = "Direct_Sales"
ALL_SEGMENTS = SEGMENTS + [MANUAL_SEGMENT]

EU_COUNTRIES = {
    "Austria", "Belgium", "Cyprus", "Czech Republic", "Denmark", "EIRE", "Finland",
    "France", "Germany", "Greece", "Italy", "Lithuania", "Malta", "Netherlands",
    "Poland", "Portugal", "Spain", "Sweden", "European Community",
}
# Postage, fees, manual adjustments and test codes are not product revenue
NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES",
    "AMAZONFEE", "CRUK", "PADS", "ADJUST", "ADJUST2", "TEST001", "TEST002",
}

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"
CACHE = DATA_DIR / "daily_revenue.csv"

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
MIRROR_URL = (
    "https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/"
    "master/data/retail-data/all/online-retail-dataset.csv"
)

COLORS = {"UK": "#2E5A88", "EU": "#5B8DB8", "RoW": "#A7C4DD", MANUAL_SEGMENT: "#D9902F"}


# --- Data -------------------------------------------------------------------
def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def load_raw() -> pd.DataFrame:
    try:
        archive = zipfile.ZipFile(io.BytesIO(_download(UCI_URL)))
        xlsx = next(name for name in archive.namelist() if name.endswith(".xlsx"))
        sheets = pd.read_excel(
            archive.open(xlsx), sheet_name=None, dtype={"Invoice": str, "StockCode": str}
        )
        raw = pd.concat(sheets.values(), ignore_index=True)
        print(f"Loaded Online Retail II from UCI: {len(raw):,} rows")
    except Exception as exc:
        print(f"UCI download failed ({exc!r}); using the public mirror")
        raw = pd.read_csv(
            io.BytesIO(_download(MIRROR_URL)), dtype={"InvoiceNo": str, "StockCode": str}
        ).rename(columns={"InvoiceNo": "Invoice", "UnitPrice": "Price", "CustomerID": "Customer ID"})
        print(f"Loaded Online Retail from mirror: {len(raw):,} rows")
    return raw


def to_segment(country: pd.Series) -> np.ndarray:
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
        ~df["Invoice"].str.startswith("C")        # cancellations
        & (df["Quantity"] > 0)
        & (df["Price"] > 0)
        & ~df["StockCode"].isin(NON_PRODUCT_CODES)
    ]
    df["date"] = pd.to_datetime(df["InvoiceDate"]).dt.normalize()
    df["segment"] = to_segment(df["Country"])
    df["revenue"] = df["Quantity"] * df["Price"]
    return df.groupby(["date", "segment"], as_index=False)["revenue"].sum()


def load_daily() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_csv(CACHE, parse_dates=["date"])
    DATA_DIR.mkdir(exist_ok=True)
    daily = build_daily(load_raw())
    daily.to_csv(CACHE, index=False)
    return daily


def monthly_history(daily: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        daily.assign(month=daily["date"].dt.to_period("M").dt.to_timestamp())
        .pivot_table(index="month", columns="segment", values="revenue", aggfunc="sum", fill_value=0)
        [SEGMENTS]
    )
    monthly["total"] = monthly.sum(axis=1)

    # Drop the trailing partial month
    last_day = daily["date"].max()
    if last_day != last_day + pd.offsets.MonthEnd(0):
        monthly = monthly[monthly.index < last_day.to_period("M").to_timestamp()]
    return monthly


# --- Planning ---------------------------------------------------------------
def estimate_organic_growth(monthly: pd.DataFrame) -> float:
    if ORGANIC_GROWTH != "auto":
        return float(ORGANIC_GROWTH)
    if len(monthly) < 24:
        print(
            f"Warning: only {len(monthly)} complete months of history; "
            "24 are needed to estimate organic growth. Using 1.0."
        )
        return 1.0
    return monthly["total"].iloc[-12:].sum() / monthly["total"].iloc[-24:-12].sum()


def build_base(monthly: pd.DataFrame, plan_months: pd.DatetimeIndex) -> pd.DataFrame:
    """For every plan month: the latest actual of the same calendar month, by segment."""
    rows = []
    for month in plan_months:
        same_month = monthly[monthly.index.month == month.month]
        if same_month.empty:
            raise ValueError(f"No history for calendar month {month.month}")
        source_month = same_month.index.max()
        row = {
            "dt": month,
            "source_month": source_month,
            "lag_years": month.year - source_month.year,
        }
        for segment in SEGMENTS:
            row[f"{segment}_actual"] = same_month.loc[source_month, segment]
        rows.append(row)
    return pd.DataFrame(rows)


def build_plan(base: pd.DataFrame, organic_growth: float):
    plan = pd.DataFrame({"dt": base["dt"]})

    # 1. Base: same-month actual grown by organic growth for each year of lag
    growth_factor = organic_growth ** base["lag_years"]
    for segment in SEGMENTS:
        plan[f"{segment}_base"] = (base[f"{segment}_actual"] * growth_factor).round()
    programmatic_base = plan[[f"{s}_base" for s in SEGMENTS]].sum(axis=1)

    # Reference period for the YoY target: the 12 months right before the plan year
    last_year_factor = organic_growth ** (base["lag_years"] - 1)
    last_year_total = sum(
        (base[f"{s}_actual"] * last_year_factor).round().sum() for s in SEGMENTS
    )

    # 2. Uplift: the gap between the YoY target and the organic base
    total_uplift = last_year_total * YOY_TARGET - programmatic_base.sum()
    if total_uplift < 0:
        print("Warning: organic growth alone is above the YoY target.")
    uplift_rate = total_uplift / programmatic_base.sum()

    # 3. Rounding reconciliation: whole pounds everywhere; the yearly residual goes
    #    to the last month, the monthly residual goes to the last segment
    uplift = (programmatic_base * uplift_rate).round()
    uplift.iloc[-1] += round(total_uplift) - uplift.sum()

    for segment in SEGMENTS[:-1]:
        plan[f"{segment}_uplift"] = (plan[f"{segment}_base"] * uplift_rate).round()
    plan[f"{SEGMENTS[-1]}_uplift"] = uplift - plan[[f"{s}_uplift" for s in SEGMENTS[:-1]]].sum(axis=1)

    # 4. Direct Sales: manual plan on top, outside the YoY target
    plan[f"{MANUAL_SEGMENT}_base"] = DIRECT_SALES
    plan[f"{MANUAL_SEGMENT}_uplift"] = 0

    for segment in ALL_SEGMENTS:
        plan[f"{segment}_total"] = plan[f"{segment}_base"] + plan[f"{segment}_uplift"]

    plan["base"] = plan[[f"{s}_base" for s in ALL_SEGMENTS]].sum(axis=1)
    plan["uplift"] = uplift
    plan["plan"] = plan["base"] + plan["uplift"]

    columns = ["dt", "plan", "base", "uplift"] + [
        f"{s}_{kind}" for s in ALL_SEGMENTS for kind in ("total", "base", "uplift")
    ]
    plan = plan[columns].astype({c: "int64" for c in columns[1:]})
    return plan, last_year_total, uplift_rate


def check_plan(plan: pd.DataFrame, last_year_total: float) -> float:
    for kind, line in (("total", "plan"), ("base", "base"), ("uplift", "uplift")):
        segments_sum = plan[[f"{s}_{kind}" for s in ALL_SEGMENTS]].sum(axis=1)
        assert (segments_sum == plan[line]).all(), f"Segment {kind} does not add up to {line}"
    assert (plan["plan"] == plan["base"] + plan["uplift"]).all()

    programmatic_plan = plan["plan"] - plan[f"{MANUAL_SEGMENT}_total"]
    achieved_yoy = programmatic_plan.sum() / last_year_total
    assert abs(achieved_yoy - YOY_TARGET) < 1e-6, achieved_yoy
    return achieved_yoy


# --- Outputs ----------------------------------------------------------------
def plot_overview(monthly: pd.DataFrame, plan: pd.DataFrame, organic_growth: float):
    programmatic_base = plan["base"] - plan[f"{MANUAL_SEGMENT}_base"]
    programmatic_plan = plan["plan"] - plan[f"{MANUAL_SEGMENT}_total"]
    fmt_k = mtick.FuncFormatter(lambda x, _: f"£{x / 1e3:,.0f}k")

    fig, (ax_line, ax_bar) = plt.subplots(
        1, 2, figsize=(15, 5.2), gridspec_kw={"width_ratios": [1.45, 1]}
    )

    # Left: actuals, then base and plan starting from the last actual month
    link = monthly.index[-1:].append(pd.DatetimeIndex(plan["dt"]))
    last_actual = monthly["total"].iloc[-1]
    ax_line.plot(monthly.index, monthly["total"], color="#1F2937", lw=2.2, label="Actual")
    ax_line.plot(
        link, np.r_[last_actual, programmatic_base], color="#6B7280", lw=1.8, ls="--",
        label=f"Organic base (×{organic_growth:.3f} YoY)",
    )
    ax_line.plot(
        link, np.r_[last_actual, programmatic_plan], color="#2E5A88", lw=2.6,
        label=f"Programmatic plan (×{YOY_TARGET} YoY)",
    )
    ax_line.fill_between(
        plan["dt"], programmatic_base, programmatic_plan, color="#2E5A88", alpha=0.12,
        label="Initiatives uplift",
    )
    ax_line.axvspan(plan["dt"].iloc[0] - pd.Timedelta(days=15), plan["dt"].iloc[-1] + pd.Timedelta(days=15),
                    color="#F3F4F6", zorder=0)
    ax_line.text(plan["dt"].iloc[0], 30_000, " plan year", color="#6B7280", fontsize=9)
    ax_line.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax_line.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax_line.set_ylim(0, None)
    ax_line.set_title("Programmatic revenue: history and plan", loc="left", fontweight="bold")
    ax_line.legend(frameon=False, loc="upper left")

    # Right: plan by segment, Direct Sales on top
    labels = [f"{d:%b}\n{d:%Y}" if i == 0 or d.month == 1 else f"{d:%b}" for i, d in enumerate(plan["dt"])]
    bottom = np.zeros(len(plan))
    for segment in ALL_SEGMENTS:
        values = plan[f"{segment}_total"].to_numpy()
        ax_bar.bar(labels, values, bottom=bottom, color=COLORS[segment], width=0.72,
                   label=segment.replace("_", " "))
        bottom += values
    ax_bar.set_title("Total plan by segment", loc="left", fontweight="bold")
    ax_bar.legend(frameon=False, ncol=4, loc="upper left", fontsize=9)
    ax_bar.set_ylim(0, bottom.max() * 1.15)

    for ax in (ax_line, ax_bar):
        ax.yaxis.set_major_formatter(fmt_k)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    fig.tight_layout(w_pad=4)
    return fig


def export_excel(plan, monthly, plan_months, organic_growth, uplift_rate, path):
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header = workbook.add_format({
            "bold": True, "font_color": "white", "bg_color": "#2F3E52",
            "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1,
        })
        number = workbook.add_format({"num_format": "#,##0", "border": 1})
        month_format = workbook.add_format({"num_format": "mmm yyyy", "border": 1, "align": "center"})
        total_format = workbook.add_format(
            {"num_format": "#,##0", "border": 1, "bold": True, "bg_color": "#EDEFF2"}
        )

        sheet = workbook.add_worksheet("Plan")
        columns = list(plan.columns)
        for col, name in enumerate(columns):
            sheet.write(0, col, "month" if name == "dt" else name.replace("_", " "), header)
        for row, record in enumerate(plan.itertuples(index=False), start=1):
            sheet.write_datetime(row, 0, record[0].to_pydatetime(), month_format)
            for col, value in enumerate(record[1:], start=1):
                sheet.write_number(row, col, value, number)

        total_row = len(plan) + 1
        sheet.write(total_row, 0, "TOTAL", total_format)
        for col, name in enumerate(columns[1:], start=1):
            letter = xl_col_to_name(col)
            sheet.write_formula(
                total_row, col, f"=SUM({letter}2:{letter}{total_row})",
                total_format, plan[name].sum(),
            )
        sheet.set_row(0, 32)
        sheet.set_column(0, 0, 11)
        sheet.set_column(1, len(columns) - 1, 13)
        sheet.freeze_panes(1, 1)

        reference = (
            f"{plan_months[0] - pd.DateOffset(years=1):%Y-%m} – "
            f"{plan_months[-1] - pd.DateOffset(years=1):%Y-%m}"
        )
        pd.DataFrame({
            "parameter": [
                "Revenue", "Plan period", "Reference period (YoY)", "YoY target",
                "Organic growth per year", "Uplift on top of base", "Direct Sales, year",
            ],
            "value": [
                "gross, GBP", f"{plan_months[0]:%Y-%m} – {plan_months[-1]:%Y-%m}", reference,
                YOY_TARGET, round(organic_growth, 4), f"{uplift_rate:.2%}", sum(DIRECT_SALES),
            ],
        }).to_excel(writer, sheet_name="Assumptions", index=False)
        writer.sheets["Assumptions"].set_column(0, 1, 26)

        history = monthly.round(0).astype("int64").reset_index()
        history["month"] = history["month"].dt.strftime("%Y-%m")
        history.to_excel(writer, sheet_name="History", index=False)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    daily = load_daily()
    print(f"Daily data: {daily['date'].min():%Y-%m-%d} → {daily['date'].max():%Y-%m-%d}, {len(daily):,} rows")

    monthly = monthly_history(daily)
    start = (
        monthly.index[-1] + pd.offsets.MonthBegin(1) if PLAN_START == "auto" else pd.Timestamp(PLAN_START)
    )
    plan_months = pd.date_range(start, periods=PLAN_MONTHS, freq="MS")
    organic_growth = estimate_organic_growth(monthly)

    base = build_base(monthly, plan_months)
    plan, last_year_total, uplift_rate = build_plan(base, organic_growth)
    achieved_yoy = check_plan(plan, last_year_total)

    programmatic_base = plan["base"].sum() - plan[f"{MANUAL_SEGMENT}_base"].sum()
    print(f"Plan period: {plan_months[0]:%Y-%m} – {plan_months[-1]:%Y-%m}")
    print("Programmatic, GBP")
    print(f"  Previous 12 months: {last_year_total:>14,.0f}")
    print(f"  Organic growth:     {programmatic_base - last_year_total:>14,.0f}   (×{organic_growth:.3f})")
    print(f"  Initiatives uplift: {plan['uplift'].sum():>14,.0f}   (+{uplift_rate:.2%} on base)")
    print(f"  Plan:               {programmatic_base + plan['uplift'].sum():>14,.0f}   (YoY ×{achieved_yoy:.3f})")
    print(f"Direct Sales:         {plan[f'{MANUAL_SEGMENT}_total'].sum():>14,.0f}")
    print(f"Total plan:           {plan['plan'].sum():>14,.0f}")
    print("All checks passed ✓")

    fig = plot_overview(monthly, plan, organic_growth)
    fig.savefig(OUTPUT_DIR / "plan_overview.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    xlsx_path = OUTPUT_DIR / f"revenue_plan_{plan_months[0]:%Y-%m}_{plan_months[-1]:%Y-%m}.xlsx"
    export_excel(plan, monthly, plan_months, organic_growth, uplift_rate, xlsx_path)
    print(f"Saved → output/{xlsx_path.name}, output/plan_overview.png")


if __name__ == "__main__":
    matplotlib.use("Agg")
    main()
