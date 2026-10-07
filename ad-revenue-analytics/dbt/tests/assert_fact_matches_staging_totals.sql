-- Aggregating to the fact grain must not lose or duplicate delivery.

with staging as (

    select report_date, sum(impressions) as impressions, sum(revenue) as revenue
    from {{ ref('stg_auction__delivery') }}
    group by report_date

),

fact as (

    select report_date, sum(impressions) as impressions, sum(revenue) as revenue
    from {{ ref('fct_ad_delivery_daily') }}
    group by report_date

)

select
    staging.report_date,
    staging.impressions as staging_impressions,
    fact.impressions    as fact_impressions,
    staging.revenue     as staging_revenue,
    fact.revenue        as fact_revenue
from staging
full outer join fact
    on fact.report_date = staging.report_date
where fact.report_date is null
   or staging.report_date is null
   or fact.impressions <> staging.impressions
   or abs(fact.revenue - staging.revenue) > 0.01
