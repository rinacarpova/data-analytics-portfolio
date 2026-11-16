# Why the KYC Pass Rate Is Falling

An investigation into a declining KYC (identity verification) pass rate, based on identity-verification vendor check results for 25.07–22.09.2023.

- [`KYC_analysis_notebook.ipynb`](KYC_analysis_notebook.ipynb): the full analysis in Python / Jupyter.
- [`KYC_pass_rate_presentation.pdf`](KYC_pass_rate_presentation.pdf): a 10-slide summary of the findings and recommendations.

## What the notebook covers

1. Data quality checks: column overview, table joins, date coverage, consistency of final statuses, missing values, year of birth.
2. The pass-rate metric and its daily and weekly dynamics, with day-to-day noise separated from the trend.
3. Hypothesis testing: which check stage loses users, whether the drops look like vendor outages, whether the country mix shifted, and what is driving the decline in Mexico.
4. A decomposition of the pass-rate drop into one-off rejection spikes and a gradual decline in Mexico.
5. Data and compliance findings, such as minors who passed KYC and passes with incomplete sanctions screening.

## Data

The source files (`KYC_summary.csv`, `KYC_details.csv`) are not included in this repository, so the notebook is published with its outputs.
