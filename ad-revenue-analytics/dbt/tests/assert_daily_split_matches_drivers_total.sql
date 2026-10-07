-- The daily split is built from the fact table, the drivers mart from the per-dimension
-- daily totals. Both must see the same days, revenue and baseline, and the daily split's
-- effects must add up to its revenue change.

with daily as (

    select * from {{ ref('mart_revenue_change_daily') }}

),

drivers_total as (

    select * from {{ ref('mart_revenue_change_drivers') }}
    where dimension = 'total'

)

select
    coalesce(daily.report_date, drivers_total.report_date)  as report_date,
    daily.revenue                                           as daily_revenue,
    drivers_total.revenue                                   as drivers_revenue,
    daily.baseline_revenue                                  as daily_baseline_revenue,
    drivers_total.baseline_revenue                          as drivers_baseline_revenue,
    daily.revenue_delta
        - daily.traffic_effect - daily.mix_effect - daily.rate_effect - daily.unattributed_effect
                                                            as unexplained_delta
from daily
full outer join drivers_total
    on drivers_total.report_date = daily.report_date
where daily.report_date is null
   or drivers_total.report_date is null
   or abs(daily.revenue - drivers_total.revenue) > 0.01
   or abs(daily.baseline_revenue - drivers_total.baseline_revenue) > 0.01
   or abs(daily.revenue_delta - daily.traffic_effect - daily.mix_effect
          - daily.rate_effect - daily.unattributed_effect) > 0.000001
