# Data traps

Found by profiling the source and by the dbt tests of ad-revenue-analytics. Each has a
decision in the model; follow it in answers.

| Trap | What is true | What to do |
|---|---|---|
| Rows that look like duplicates | 16.5K combinations of all 12 dimension columns occur more than once (86K rows), mostly with different metrics: the export is at a finer grain than its columns. Fully identical rows also exist, but they hold a negligible share of revenue. | Never deduplicate. Sum all rows. If asked, quantify what deduplication would lose. |
| Zero-impression rows | A third of raw rows (190K) have no impressions and practically no revenue. | Kept in staging, dropped from the fact table when a slice has nothing else. Totals don't change. |
| Negative revenue | One raw row has revenue −0.15 (an adjustment). | Keep it, so totals match the source. |
| Viewable > measurable | 2.2K rows, mostly channel 19 / ad type 17. | Keep them; overall viewability moves ~0.7 pp without them. |
| `revenue_share_percent` | 1.0 in every row (a fraction, despite the name). | Revenue is used as reported; no net/gross adjustment. |
| `integration_type_id` | A single value. | Carries no information. |
| Channel 2 | Delivers impressions with zero revenue. | eCPM is 0. Mention it when channel 2 appears in an answer. |
| Averaged ratios | `fct_ad_delivery_daily.ecpm` is a row-level ratio; most rows are small slices with low eCPM. | `avg(ecpm)` is far from the true eCPM. Always sum, then divide. |
| Trailing-7-day baseline | Weekly pattern: Wed and Sat get ~35% fewer impressions than Mon and Thu. | Compare with the same weekday of previous weeks (marts already do). |
| No baseline before 15 June | The baseline needs 2 previous same weekdays. | For 1–14 June, compare raw days only if asked, and say it is not the standard baseline. |
| A mid-June eCPM dip | The week of 10 June averaged eCPM 1.88 against 2.08 the week before; it sits inside late-June baselines. | Late-June rate effects partly include a rebound; mention when rate drives a late-June change. |
| One event, several alerts | A slice that is one advertiser on one ad unit in one channel alerts on each dimension. | Group same-day alerts by the delivery they describe. |
| Alert date ≠ event date | Alerts can fire only from 15 June (the first day with a baseline). | Check the slice's daily series in `int_delivery__by_dimension_daily` for the real start. |
| Retrospective thresholds | Alert thresholds use the error over all of 15–30 June, including the anomalous days. | Call the alert feed a retrospective scan, not a production backtest. |
