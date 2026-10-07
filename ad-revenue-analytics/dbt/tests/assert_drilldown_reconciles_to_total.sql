-- Every drill-down dimension must split the day's total without gaps or double counting.

with by_dimension as (

    select
        report_date,
        dimension,
        sum(impressions)    as impressions,
        sum(revenue)        as revenue
    from {{ ref('int_delivery__by_dimension_daily') }}
    group by report_date, dimension

),

totals as (

    select report_date, impressions, revenue
    from by_dimension
    where dimension = 'total'

)

select
    by_dimension.*,
    totals.impressions  as total_impressions,
    totals.revenue      as total_revenue
from by_dimension
inner join totals
    on totals.report_date = by_dimension.report_date
where by_dimension.impressions <> totals.impressions
   or abs(by_dimension.revenue - totals.revenue) > 0.01
