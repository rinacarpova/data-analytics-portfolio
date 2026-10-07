-- Daily revenue change against the same-weekday baseline, split three ways:
--   traffic = the change in total impressions, priced at the average total eCPM
--   mix     = impressions moving between slices with different eCPM,
--             e.g. more traffic on an expensive site
--   rate    = the same slice earning a different eCPM
-- Slices are the fact grain. Each slice's change is split into volume and rate
-- (macros/revenue_split.sql); the slice volume effects add up to traffic + mix,
-- so mix is what remains of them once the traffic effect is taken out.

{%- set baseline_weeks = var('baseline_weeks') %}
{%- set min_baseline_weeks = var('min_baseline_weeks') %}
{%- set slice_columns = [
    'site_id', 'ad_unit_id', 'ad_type_id', 'monetization_channel_id',
    'advertiser_id', 'geo_id', 'device_category_id', 'os_id'
] %}

with delivery as (

    select
        report_date,
        md5(concat_ws('|', {{ slice_columns | join(', ') }}))   as slice_key,
        impressions,
        revenue
    from {{ ref('fct_ad_delivery_daily') }}

),

date_spine as (

    select
        cast(unnest(generate_series(
            cast(min(report_date) as timestamp),
            cast(max(report_date) as timestamp),
            interval 1 day
        )) as date) as report_date
    from delivery

),

-- The same weekday 1..baseline_weeks weeks back, within the data.
baseline_dates as (

    select
        date_spine.report_date,
        date_spine.report_date - cast(7 * weeks.weeks_back as integer)  as baseline_date
    from date_spine
    cross join range(1, {{ baseline_weeks }} + 1) as weeks(weeks_back)
    where date_spine.report_date - cast(7 * weeks.weeks_back as integer) >= (select min(report_date) from date_spine)

),

comparable_days as (

    select
        report_date,
        count(*) as baseline_weeks
    from baseline_dates
    group by report_date
    having count(*) >= {{ min_baseline_weeks }}

),

current_day as (

    select
        delivery.report_date,
        delivery.slice_key,
        sum(delivery.impressions)   as impressions,
        sum(delivery.revenue)       as revenue
    from delivery
    inner join comparable_days
        on comparable_days.report_date = delivery.report_date
    group by delivery.report_date, delivery.slice_key

),

baseline as (

    select
        baseline_dates.report_date,
        delivery.slice_key,
        sum(delivery.impressions) / any_value(comparable_days.baseline_weeks)   as impressions,
        sum(delivery.revenue) / any_value(comparable_days.baseline_weeks)       as revenue
    from baseline_dates
    inner join comparable_days
        on comparable_days.report_date = baseline_dates.report_date
    inner join delivery
        on delivery.report_date = baseline_dates.baseline_date
    group by baseline_dates.report_date, delivery.slice_key

),

slices as (

    select
        coalesce(current_day.report_date, baseline.report_date)    as report_date,
        coalesce(current_day.impressions, 0)                        as impressions,
        coalesce(current_day.revenue, 0)                            as revenue,
        coalesce(baseline.impressions, 0)                           as baseline_impressions,
        coalesce(baseline.revenue, 0)                               as baseline_revenue
    from current_day
    full outer join baseline
        on  baseline.report_date = current_day.report_date
        and baseline.slice_key = current_day.slice_key

),

slice_effects as (

    select
        *,
        revenue - baseline_revenue                                              as revenue_delta,
        {{ safe_divide('revenue * 1000', 'impressions') }}                      as ecpm,
        {{ safe_divide('baseline_revenue * 1000', 'baseline_impressions') }}    as baseline_ecpm
    from slices

),

daily as (

    select
        report_date,
        sum(impressions)            as impressions,
        sum(baseline_impressions)   as baseline_impressions,
        sum(revenue)                as revenue,
        sum(baseline_revenue)       as baseline_revenue,
        sum({{ volume_effect('impressions', 'baseline_impressions', 'ecpm', 'baseline_ecpm') }})  as slice_volume_effect,
        sum({{ rate_effect('impressions', 'baseline_impressions', 'ecpm', 'baseline_ecpm') }})    as rate_effect,
        sum({{ unattributed_effect('revenue_delta', 'ecpm', 'baseline_ecpm') }})                  as unattributed_effect
    from slice_effects
    group by report_date

),

daily_with_ecpm as (

    select
        *,
        {{ safe_divide('revenue * 1000', 'impressions') }}                      as ecpm,
        {{ safe_divide('baseline_revenue * 1000', 'baseline_impressions') }}    as baseline_ecpm
    from daily

),

with_traffic as (

    select
        *,
        {{ volume_effect('impressions', 'baseline_impressions', 'ecpm', 'baseline_ecpm') }} as traffic_effect
    from daily_with_ecpm

)

select
    with_traffic.report_date,
    comparable_days.baseline_weeks,
    impressions,
    baseline_impressions,
    ecpm,
    baseline_ecpm,
    revenue,
    baseline_revenue,
    revenue - baseline_revenue                  as revenue_delta,
    traffic_effect,
    slice_volume_effect - traffic_effect        as mix_effect,
    rate_effect,
    unattributed_effect
from with_traffic
inner join comparable_days
    on comparable_days.report_date = with_traffic.report_date
