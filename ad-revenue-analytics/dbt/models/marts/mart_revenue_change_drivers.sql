-- What moved revenue against the same-weekday baseline, for every slice of every drill-down dimension.
-- The change of each slice is split into volume (impressions) and price (eCPM) effects;
-- see macros/revenue_split.sql for the method.

with slices as (

    select *
    from {{ ref('int_delivery__vs_baseline') }}
    where revenue <> 0 or baseline_revenue <> 0

),

with_ecpm as (

    select
        *,
        revenue - baseline_revenue                                              as revenue_delta,
        {{ safe_divide('revenue * 1000', 'impressions') }}                      as ecpm,
        {{ safe_divide('baseline_revenue * 1000', 'baseline_impressions') }}    as baseline_ecpm
    from slices

)

select
    report_date,
    dimension,
    dimension_value,
    baseline_weeks,
    impressions,
    baseline_impressions,
    ecpm,
    baseline_ecpm,
    revenue,
    baseline_revenue,
    revenue_delta,
    {{ volume_effect('impressions', 'baseline_impressions', 'ecpm', 'baseline_ecpm') }}    as volume_effect,
    {{ rate_effect('impressions', 'baseline_impressions', 'ecpm', 'baseline_ecpm') }}      as price_effect,
    {{ unattributed_effect('revenue_delta', 'ecpm', 'baseline_ecpm') }}                    as unattributed_effect,
    revenue_delta / nullif(sum(revenue_delta) over (partition by report_date, dimension), 0)
                                                                                            as share_of_total_delta,
    row_number() over (
        partition by report_date, dimension
        order by abs(revenue_delta) desc, dimension_value
    )                                                                                       as driver_rank
from with_ecpm
