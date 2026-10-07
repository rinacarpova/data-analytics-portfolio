-- The labels file covers every NAB series; only the ad exchange ones are kept.

with source as (

    select json from {{ source('nab', 'anomaly_windows') }}

),

series as (

    select
        unnest(json_keys(json)) as series_file,
        json
    from source

),

windows as (

    select
        series_file,
        unnest(cast(json_extract(json, '$."' || series_file || '"') as varchar[][])) as anomaly_window
    from series
    where series_file like 'realAdExchange/%'

)

select
    regexp_extract(series_file, '(exchange-\d+)_(cpc|cpm)', 1)          as exchange,
    upper(regexp_extract(series_file, '(exchange-\d+)_(cpc|cpm)', 2))   as metric,
    cast(anomaly_window[1] as timestamp)                                 as window_start,
    cast(anomaly_window[2] as timestamp)                                 as window_end
from windows
