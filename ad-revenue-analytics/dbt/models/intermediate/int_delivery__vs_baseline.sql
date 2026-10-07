-- Each day of each slice next to its baseline: the average of the same weekday over the
-- previous weeks. Delivery has a strong weekly pattern, so a Wednesday is compared with
-- previous Wednesdays rather than with the last 7 days, which keeps the day of the week
-- out of the change. The trailing 7-day average is kept as a reference column for
-- comparing the two baselines.
-- Days without delivery are filled with zeros first, so a slice that stops delivering
-- still shows up as a drop instead of disappearing, and the weekday windows stay aligned.

{%- set baseline_weeks = var('baseline_weeks') %}
{%- set min_baseline_weeks = var('min_baseline_weeks') %}

with daily as (

    select * from {{ ref('int_delivery__by_dimension_daily') }}

),

date_spine as (

    select
        cast(unnest(generate_series(
            cast(min(report_date) as timestamp),
            cast(max(report_date) as timestamp),
            interval 1 day
        )) as date) as report_date
    from daily

),

slices as (

    select distinct dimension, dimension_value
    from daily

),

filled as (

    select
        date_spine.report_date,
        slices.dimension,
        slices.dimension_value,
        coalesce(daily.impressions, 0)  as impressions,
        coalesce(daily.revenue, 0)      as revenue
    from date_spine
    cross join slices
    left join daily
        on  daily.report_date = date_spine.report_date
        and daily.dimension = slices.dimension
        and daily.dimension_value = slices.dimension_value

),

with_baseline as (

    select
        *,
        avg(impressions) over same_weekday  as baseline_impressions,
        avg(revenue) over same_weekday      as baseline_revenue,
        count(*) over same_weekday          as baseline_weeks,
        avg(revenue) over trailing_week     as trailing_7d_revenue
    from filled
    window
        same_weekday as (
            partition by dimension, dimension_value, dayofweek(report_date)
            order by report_date
            rows between {{ baseline_weeks }} preceding and 1 preceding
        ),
        trailing_week as (
            partition by dimension, dimension_value
            order by report_date
            rows between 7 preceding and 1 preceding
        )

)

select
    report_date,
    dimension,
    dimension_value,
    impressions,
    revenue,
    baseline_impressions,
    baseline_revenue,
    baseline_weeks,
    trailing_7d_revenue
from with_baseline
where baseline_weeks >= {{ min_baseline_weeks }}
