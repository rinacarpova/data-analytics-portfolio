# Metrics

Every ratio is computed from sums over the rows in scope. Never average a ratio column.

| Metric | Definition | SQL over `fct_ad_delivery_daily` |
|---|---|---|
| Revenue | Sum of reported revenue | `sum(revenue)` |
| Impressions | Sum of impressions | `sum(impressions)` |
| eCPM | Revenue per 1,000 impressions | `sum(revenue) * 1000 / nullif(sum(impressions), 0)` |
| Viewability rate | Viewable / measurable | `sum(viewable_impressions) / nullif(sum(measurable_impressions), 0)` |
| Measurability rate | Measurable / all | `sum(measurable_impressions) / nullif(sum(impressions), 0)` |
| Share of revenue | Slice revenue / total revenue in the same period | `sum(revenue) / sum(sum(revenue)) over ()` |

## Revenue change

The baseline of a day is the average of the **same weekday** over up to 3 previous weeks
(at least 2 required), so it exists for 15–30 June only. On this data it misses daily revenue
by ~11% (WAPE) against ~16% for a trailing 7-day average.

Per slice, with averages of the two periods (midpoint split, no interaction term):

```
volume_effect = (impressions - baseline_impressions) * avg(ecpm, baseline_ecpm) / 1000
price_effect  = (ecpm - baseline_ecpm) * avg(impressions, baseline_impressions) / 1000
revenue_delta = volume_effect + price_effect + unattributed_effect
```

For the whole day, at the full fact grain:

```
traffic = Δ total impressions × average total eCPM / 1000
mix     = Σ slice volume effects − traffic
rate    = Σ slice price effects
```

Read: traffic = more impressions overall; mix = impressions shifting toward better- or
worse-paid inventory; rate = the same inventory paid more or less.

## Patterns

Share of a dimension in a period:

```sql
select monetization_channel_id,
       sum(revenue) as revenue,
       sum(revenue) / sum(sum(revenue)) over () as revenue_share
from fct_ad_delivery_daily
group by 1
order by 2 desc
```

A day's top drivers, all dimensions:

```sql
select dimension, dimension_value, revenue_delta, volume_effect, price_effect
from mart_revenue_change_drivers
where report_date = date '2019-06-20' and dimension <> 'total' and driver_rank <= 3
order by dimension, driver_rank
```

Daily series of one slice (when did it start / stop):

```sql
select report_date, impressions, revenue
from int_delivery__by_dimension_daily
where dimension = 'site_id' and dimension_value = '346'
order by report_date
```
