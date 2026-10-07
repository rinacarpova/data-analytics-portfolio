with source as (

    select * from {{ source('real_time_auction', 'delivery') }}

)

select
    cast("date" as date)                    as report_date,
    site_id,
    ad_unit_id,
    ad_type_id,
    monetization_channel_id,
    integration_type_id,
    advertiser_id,
    order_id,
    line_item_type_id,
    geo_id,
    device_category_id,
    os_id,
    cast(total_impressions as bigint)       as impressions,
    cast(total_revenue as double)           as revenue,
    cast(viewable_impressions as bigint)    as viewable_impressions,
    cast(measurable_impressions as bigint)  as measurable_impressions,
    cast(revenue_share_percent as double)   as revenue_share_percent
from source
