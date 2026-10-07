-- exchange-2 reports the hour 2011-08-24 12:00 twice with different values in both
-- series; the two readings are averaged so each series has one value per hour.

with source as (

    select * from {{ source('nab', 'exchange_metrics') }}

),

parsed as (

    select
        regexp_extract(filename, '(exchange-\d+)_(cpc|cpm)_results', ['exchange', 'metric']) as series,
        cast("timestamp" as timestamp)  as observed_at,
        cast(value as double)           as metric_value
    from source

)

select
    series.exchange         as exchange,
    upper(series.metric)    as metric,
    observed_at,
    avg(metric_value)       as metric_value
from parsed
group by all
