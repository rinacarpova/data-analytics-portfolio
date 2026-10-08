# Models

All tables live in the `main` schema of `ad-revenue-analytics/data/ad_revenue.duckdb`, built
by `dbt build`. Lineage: `stg_` → `int_` → `fct_` / `mart_`.

## Publisher delivery

### `fct_ad_delivery_daily`: the main fact table

Grain: `report_date × site_id × ad_unit_id × ad_type_id × monetization_channel_id ×
advertiser_id × geo_id × device_category_id × os_id` (unique `delivery_key`). ~258K rows.

| Column | Meaning |
|---|---|
| `delivery_key` | md5 hash of the grain columns |
| `report_date` | Day, 2019-06-01 to 2019-06-30 |
| `site_id`, `ad_unit_id`, `ad_type_id`, `monetization_channel_id`, `advertiser_id`, `geo_id`, `device_category_id`, `os_id` | Anonymised integer IDs |
| `impressions` | Total impressions |
| `revenue` | Revenue as reported (currency unknown); can be negative where the source has an adjustment |
| `viewable_impressions` | Viewable by the MRC standard (50% of pixels for 1 second) |
| `measurable_impressions` | Impressions where viewability could be measured |
| `ecpm`, `viewability_rate`, `measurability_rate` | Row-level ratios. **Do not average them**; recompute from sums |

`order_id`, `line_item_type_id` and `integration_type_id` are aggregated away here.

Monetisation channels (IDs only; the meaning of each ID is not published): the source
describes the channel set as header bidding, dynamic allocation, exchange bidding and direct.

### `mart_revenue_change_daily`: the day against its baseline

One row per day, **2019-06-15 to 2019-06-30**.

| Column | Meaning |
|---|---|
| `baseline_weeks` | 2 or 3: how many previous same weekdays the baseline averages |
| `impressions`, `baseline_impressions` | Day and baseline |
| `ecpm`, `baseline_ecpm` | Day and baseline eCPM (from sums) |
| `revenue`, `baseline_revenue`, `revenue_delta` | `revenue_delta = revenue - baseline_revenue` |
| `traffic_effect` | Δ total impressions × average total eCPM / 1000 |
| `mix_effect` | Impressions moving between slices with different eCPM |
| `rate_effect` | The same slices paid differently |
| `unattributed_effect` | Revenue in slices with no impressions in either period |

`traffic + mix + rate + unattributed = revenue_delta` exactly. The split is computed at the
full fact grain.

### `mart_revenue_change_drivers`: which slices moved

Grain: `report_date × dimension × dimension_value`, 15–30 June. `dimension` is one of the
eight drill-down dimensions or `'total'` (with `dimension_value = 'total'`).
`dimension_value` is text, so filter with quotes: `dimension_value = '345'`.

| Column | Meaning |
|---|---|
| `baseline_weeks`, `impressions`, `baseline_impressions`, `ecpm`, `baseline_ecpm`, `revenue`, `baseline_revenue`, `revenue_delta` | As above, for the slice |
| `volume_effect` | Δ impressions × average eCPM of the two periods / 1000 |
| `price_effect` | Δ eCPM × average impressions of the two periods / 1000 |
| `unattributed_effect` | Revenue change in a slice with no impressions in either period |
| `share_of_total_delta` | The slice's share of its dimension's total change |
| `driver_rank` | 1 = largest absolute change within that day and dimension |

A slice that appears or disappears is all volume.

### `mart_revenue_alerts`: alerts with explanations

One row per alert (20 rows). Three rules:

| `rule` | Fires when |
|---|---|
| `total revenue` | The day's revenue is off its baseline by more than 2 × the total's usual baseline error (WAPE) |
| `stopped delivering` | A slice normally worth ≥ 1% of the day's revenue delivers < 10% of its baseline |
| `large slice moved` | A slice moved by ≥ 5% of the day's revenue and by more than 2 × its dimension's usual error |

An alert is not repeated for the same rule and slice within 7 days. Columns: `report_date`,
`rule`, `dimension`, `dimension_value`, `baseline_revenue`, `revenue`, `revenue_delta`,
`change_pct`, `share_of_day_revenue`, `change_threshold`, `volume_effect`, `price_effect`,
`main_driver` (`volume` | `price`), `alert_text`.

### `int_delivery__vs_baseline`

Grain: `report_date × dimension × dimension_value`, 15–30 June. Columns: `impressions`,
`revenue`, `baseline_impressions`, `baseline_revenue`, `baseline_weeks`,
`trailing_7d_revenue` (average of the previous 7 days, kept only to compare baselines).

### `int_delivery__by_dimension_daily`

Grain: `report_date × dimension × dimension_value`, all 30 days. Daily `impressions` and
`revenue` per value of each drill-down dimension, plus a `'total'` row. Use it for daily
series of one slice (e.g. when did a channel stop).

### `stg_auction__delivery`: the raw export

Same 567K rows as the source CSV with typed, renamed columns: `report_date`, the eight IDs,
`integration_type_id`, `order_id`, `line_item_type_id`, `impressions`, `revenue`,
`viewable_impressions`, `measurable_impressions`, `revenue_share_percent` (a fraction, 1.0
everywhere). Use only for questions about the export itself.

## Ad exchange series (not this publisher)

### `fct_exchange_metrics_hourly`

Grain: `exchange × metric × observed_at`. `exchange` ∈ exchange-2, exchange-3, exchange-4;
`metric` ∈ CPC, CPM; `metric_value`; `is_labelled_anomaly` (inside a labelled window).
July–September 2011. 14 labelled windows in `stg_nab__anomaly_windows`
(`exchange`, `metric`, `window_start`, `window_end`).
