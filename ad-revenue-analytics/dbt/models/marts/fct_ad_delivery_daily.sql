-- Daily delivery at the grain an ad ops team works with. order_id, line_item_type_id
-- and integration_type_id are aggregated away (see the source description).
-- A third of the source rows have no impressions and no revenue; slices made only
-- of such rows are left out.

with delivery as (

    select * from {{ ref('stg_auction__delivery') }}

)

select
    md5(concat_ws('|',
        report_date, site_id, ad_unit_id, ad_type_id, monetization_channel_id,
        advertiser_id, geo_id, device_category_id, os_id
    ))                                                                              as delivery_key,
    report_date,
    site_id,
    ad_unit_id,
    ad_type_id,
    monetization_channel_id,
    advertiser_id,
    geo_id,
    device_category_id,
    os_id,
    sum(impressions)                                                                as impressions,
    sum(revenue)                                                                    as revenue,
    sum(viewable_impressions)                                                       as viewable_impressions,
    sum(measurable_impressions)                                                     as measurable_impressions,
    {{ safe_divide('sum(revenue) * 1000', 'sum(impressions)') }}                    as ecpm,
    {{ safe_divide('sum(viewable_impressions)', 'sum(measurable_impressions)') }}   as viewability_rate,
    {{ safe_divide('sum(measurable_impressions)', 'sum(impressions)') }}            as measurability_rate
from delivery
group by all
having sum(impressions) > 0 or sum(revenue) <> 0
