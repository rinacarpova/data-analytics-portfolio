-- Daily totals per value of every drill-down dimension, stacked into one long table.
-- Each dimension splits the whole day, so its values add up to the 'total' row.

{%- set dimensions = var('drilldown_dimensions') %}

with delivery as (

    select * from {{ ref('stg_auction__delivery') }}

)

select
    report_date,
    'total'             as dimension,
    'total'             as dimension_value,
    sum(impressions)    as impressions,
    sum(revenue)        as revenue
from delivery
group by report_date

{%- for dimension in dimensions %}

union all

select
    report_date,
    '{{ dimension }}'                                       as dimension,
    coalesce(cast({{ dimension }} as varchar), '(null)')    as dimension_value,
    sum(impressions)                                        as impressions,
    sum(revenue)                                            as revenue
from delivery
group by report_date, {{ dimension }}
{%- endfor %}
