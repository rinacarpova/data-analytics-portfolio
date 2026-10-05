# Annual Revenue Plan by Segment

A portfolio project that builds a 12-month revenue plan by business segment from historical transactions and exports the result to Excel. It is inspired by real-world financial planning workflows in advertising monetisation and uses only public data.

## Context

I'm a Senior Data Analyst working on advertising monetisation and financial planning. This project reproduces a realistic annual revenue-planning workflow end-to-end on public data so the methodology and code can be shared safely.

## What it does

| Step | Logic |
|---|---|
| Base scenario | For each segment, each plan month starts from that segment's latest complete actual for the same calendar month, preserving seasonality. The actual is grown by organic growth measured in the data. |
| Direct Sales | A manually planned stream added on top of the plan. It is not part of the YoY target. |
| Uplift | The part of the programmatic YoY target that organic growth does not cover is treated as the expected effect of new initiatives and distributed proportionally to the base. |
| Integrity | Rounding residuals are reconciled so segments add up exactly to the plan line. Sanity checks confirm both monthly totals and the YoY target. |
| Export | Creates an Excel workbook with Plan, Assumptions and History sheets, plus a PNG overview chart. |

## Data

[Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) from the UCI Machine Learning Repository: about 1M transactions from a UK online retailer, Dec 2009 – Dec 2011, licensed CC BY 4.0.

Countries are grouped into three segments (*UK*, *EU*, *Rest of World*) that stand in for product lines. Revenue is gross, in GBP; cancelled orders are excluded rather than netted off.

The first run downloads the source data and saves a small daily aggregate to `data/daily_revenue.csv`. Later runs reuse that cache. If UCI is unavailable, the code falls back to a public mirror of the original *Online Retail* dataset.

> Citation: Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository.

## Two ways to view the project

- **`revenue_plan.ipynb`** — portfolio/presentation version. The logic is split into business steps, with explanations, intermediate tables, reconciliation checks and saved outputs visible directly on GitHub.
- **`revenue_plan.py`** — compact runnable version for executing the workflow end-to-end in one command.

### Run the script

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python revenue_plan.py
```

Or open `revenue_plan.ipynb` in Jupyter to follow the calculation step by step.

All business inputs are grouped near the top of the code: plan start, YoY target, organic growth and the Direct Sales plan.

## Assumptions and limitations

- The YoY target is a business input, not a forecast.
- Organic growth is one rate for all segments and months.
- Automatic organic-growth estimation needs 24 complete months of history; otherwise the base stays flat and a warning is printed.
- The uplift is the same percentage of the base in every month; initiatives do not ramp during the year.
- Direct Sales are a manual input added on top of the programmatic plan.
- Revenue is gross: cancellations are excluded, not subtracted.

## Structure

```
├── revenue_plan.py         # one-command runnable workflow
├── revenue_plan.ipynb      # step-by-step portfolio notebook with outputs
├── data/                   # generated cache on first run
├── output/                 # generated Excel plan + overview chart
├── requirements.txt
└── README.md
```

## Tech

Python · pandas · NumPy · matplotlib · XlsxWriter
