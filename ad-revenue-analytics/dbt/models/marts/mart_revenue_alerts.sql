-- Alerts on the publisher's daily revenue, one row per alert, each with its explanation.
--
-- Three rules, one per kind of event:
--   total revenue       the day's revenue is off its same-weekday baseline by more than
--                       alert_noise_multiple × the baseline's usual error for the total
--   stopped delivering  a slice that normally brings at least alert_min_share_stopped of the
--                       day's revenue delivered less than 10% of its baseline
--   large slice moved   a slice changed by at least alert_min_share_moved of the day's revenue
--                       and by more than alert_noise_multiple × its dimension's usual error
-- The usual error is the baseline's WAPE per dimension over the comparable days, so a noisy
-- dimension (ad units) needs a bigger move than a stable one (devices) to alert. WAPE divides by
-- actual revenue, its standard definition; on a down day that makes the error slightly larger.
-- Retrospective by design: the error is measured over all comparable days, including days after
-- an alert and the anomalous days themselves. A live monitor would estimate it from past days only.
-- An alert is raised once: while the same rule keeps firing for the same slice, or fires
-- again within alert_cooldown_days, it stays quiet.

{%- set noise_multiple = var('alert_noise_multiple') %}
{%- set min_share_moved = var('alert_min_share_moved') %}
{%- set min_share_stopped = var('alert_min_share_stopped') %}
{%- set cooldown_days = var('alert_cooldown_days') %}

with drivers as (

    select * from {{ ref('mart_revenue_change_drivers') }}

),

noise as (

    select
        dimension,
        sum(abs(revenue - baseline_revenue)) / nullif(sum(revenue), 0)  as baseline_wape
    from {{ ref('int_delivery__vs_baseline') }}
    group by dimension

),

day_totals as (

    select
        report_date,
        baseline_revenue as day_baseline_revenue
    from drivers
    where dimension = 'total'

),

slices as (

    select
        drivers.*,
        noise.baseline_wape,
        {{ safe_divide('drivers.revenue_delta', 'drivers.baseline_revenue') }}         as change_pct,
        abs(drivers.revenue_delta) / day_totals.day_baseline_revenue                    as share_of_day_revenue,
        drivers.baseline_revenue / day_totals.day_baseline_revenue                      as baseline_share_of_day
    from drivers
    inner join noise
        on noise.dimension = drivers.dimension
    inner join day_totals
        on day_totals.report_date = drivers.report_date

),

candidates as (

    select
        *,
        case
            when dimension = 'total'
                and abs(change_pct) > {{ noise_multiple }} * baseline_wape
                then 'total revenue'
            when dimension <> 'total'
                and baseline_share_of_day >= {{ min_share_stopped }}
                and revenue < 0.1 * baseline_revenue
                then 'stopped delivering'
            when dimension <> 'total'
                and share_of_day_revenue >= {{ min_share_moved }}
                and abs(change_pct) > {{ noise_multiple }} * baseline_wape
                then 'large slice moved'
        end as rule
    from slices

),

with_previous as (

    select
        *,
        lag(report_date) over (
            partition by dimension, dimension_value, rule
            order by report_date
        ) as previous_alert_date
    from candidates
    where rule is not null

)

select
    report_date,
    rule,
    dimension,
    dimension_value,
    baseline_revenue,
    revenue,
    revenue_delta,
    change_pct,
    share_of_day_revenue,
    {{ noise_multiple }} * baseline_wape                                    as change_threshold,
    volume_effect,
    price_effect,
    case when abs(price_effect) > abs(volume_effect) then 'price' else 'volume' end
                                                                            as main_driver,
    printf(
        '%s %s: revenue %+.0f%% against the same weekdays (%+.0f, %.0f%% of the day), mostly %s',
        dimension, dimension_value, 100 * change_pct, revenue_delta, 100 * share_of_day_revenue,
        case when abs(price_effect) > abs(volume_effect) then 'price (eCPM)' else 'volume (impressions)' end
    )                                                                       as alert_text
from with_previous
where previous_alert_date is null
   or report_date - previous_alert_date > {{ cooldown_days }}
